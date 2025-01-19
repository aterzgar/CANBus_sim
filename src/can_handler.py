# can_handler.py

import can
import time
import random
import threading
from vehicle_state import (
    VehicleState,
    CAN_LEFT_SIGNAL,
    CAN_RIGHT_SIGNAL,
)

# CAN Message IDs from DBC
IGNITION_ID = 0x130       # BO_ 304 TerminalStatus
ENGINE_STATUS_ID = 0x1D0  # BO_ 464 EngineData
SPEED_ID = 0x1A0          # BO_ 416 Speed
RPM_ID = 0x0AA            # BO_ 170 AccPedal
TURN_SIGNAL_ID = 0x1F6    # BO_ 502 TurnSignals
BRAKE_ID = 0x0A8          # BO_ 168 EngineAndBrake
GEAR_ID = 0x1D2           # BO_ 466 TransmissionDataDisplay
DOOR_ID = 0x24B

class CANHandler:
    def __init__(self, channel='vcan0', state: VehicleState = None):
        self.channel = channel
        if state is None:
            state = VehicleState()
        self.state = state

        # Initialize CAN IDs based on DBC
        self.speed_id = SPEED_ID
        self.rpm_id = RPM_ID
        self.signal_id = TURN_SIGNAL_ID
        self.brake_id = BRAKE_ID
        self.gear_id = GEAR_ID
        self.ignition_id = IGNITION_ID
        self.engine_status_id = ENGINE_STATUS_ID

        # Message monitoring
        self.last_messages = []
        self.max_messages = 10
        
        # Setup CAN bus
        try:
            self.bus = can.interface.Bus(channel=channel, interface='socketcan')
            self.can_enabled = True
            print("CAN Bus initialized successfully")
        except Exception as e:
            print(f"CAN Bus initialization failed: {e}")
            print("Running in simulation mode")
            self.can_enabled = False

        # Start background message thread
        self.bg_thread = threading.Thread(target=self._send_background_messages)
        self.bg_thread.daemon = True
        self.bg_thread.start()

    def send_message(self, can_id, data):
        # Send a CAN message
        if self.can_enabled:
            try:
                message = can.Message(
                    arbitration_id=can_id,
                    data=data,
                    is_extended_id=False
                )
                self.bus.send(message)
            except Exception as e:
                print(f"Error sending CAN message: {e}")
    
    def set_ignition(self, state):
        # Set ignition state
        data = [0] * 8
        if state:
            data[2] |= 0x80  # Set AccOn bit
        else:
            data[2] |= 0x40

        # Add counter and checksum as per DBC
        data[4] = self.get_counter() & 0x0F 
        data[4] |= (self.calculate_checksum(data) << 4) 
        self.send_message(IGNITION_ID, data)

    def set_engine(self, state):
        # Set engine running state
        data = [0] * 8
        if state:
            data[2] |= (2 << 4) 
        else:
            data[2] &= ~(3 << 4)
        # Set additional engine-related data
        data[0] = 0x30  # Default engine temperature
        data[4] = self.get_counter() & 0x0F 
        # Send the CAN message
        self.send_message(ENGINE_STATUS_ID, data)

    
    def update_speed(self):
        # Update vehicle speed and RPM based on acceleration, brake status, and gear position
        if not self.state.engine_running:
            self.state.current_speed = 0
            self.state.engine_rpm = 0
            return

        acceleration_rate = 2.0
        coast_decel_rate = 1.0
        brake_decel_rate = 4.0

        # Handle speed and RPM based on current gear position (0=P, 1=N, 2=R, 3=D)
        if self.state.gear_position == 0:  # P (Park)
            self.state.current_speed = 0
            self.state.engine_rpm = 800  # Idle RPM in Park
        
        elif self.state.gear_position == 1:  # N (Neutral)
            self.state.current_speed = 0  # Speed should remain 0
            if self.state.acceleration > 0:
                self.state.engine_rpm = min(3000, self.state.engine_rpm + (self.state.acceleration * 200))
            else:
                self.state.engine_rpm = max(800, self.state.engine_rpm - 100)
        
        elif self.state.gear_position == 2:  # R (Reverse)
            if self.state.acceleration > 0:
                # Increase speed up to a maximum reverse limit
                self.state.current_speed = min(30, self.state.current_speed + (self.state.acceleration * acceleration_rate))
            elif self.state.brake_active:
                # Apply brakes to reduce speed
                self.state.current_speed = max(0, self.state.current_speed - brake_decel_rate)
            else:
                # Natural deceleration
                self.state.current_speed = max(0, self.state.current_speed - coast_decel_rate)
            
            # Set engine RPM based on reverse speed
            self.state.engine_rpm = max(1200, 800 + (self.state.current_speed * 20))    
        
        elif self.state.gear_position == 3:  # D (Drive)
            if self.state.acceleration > 0:
                self.state.current_speed = min(255, self.state.current_speed + acceleration_rate)
            elif self.state.brake_active:
                self.state.current_speed = max(0, self.state.current_speed - brake_decel_rate)
            else:
                self.state.current_speed = max(0, self.state.current_speed - coast_decel_rate)
            self.state.engine_rpm = min(8000, 800 + (self.state.current_speed * 20))  # RPM increases with speed

        # Send updated speed and RPM over CAN
        self.send_speed_and_rpm(abs(self.state.current_speed), self.state.engine_rpm)

    def send_speed_and_rpm(self, speed, rpm):
        # Send vehicle speed and RPM over CAN 
        speed_data = [0] * 8
        speed_kph = int(speed / 0.103)
        
        # DBC defines speed as a 12-bit value, scale accordingly
        speed_data[0] = (speed_kph & 0xFF0) >> 4
        speed_data[1] = (speed_kph & 0x00F) << 4
        self.send_message(self.speed_id, speed_data)
        
        # Send RPM message
        rpm_data = [0] * 8
        rpm_value = int(rpm / 0.25)

        rpm_data[4] = (rpm_value >> 8) & 0xFF
        rpm_data[5] = rpm_value & 0xFF
        self.send_message(self.rpm_id, rpm_data)    
    
    def set_speed(self, speed):
        # Set vehicle speed based on gear position
        if self.state.gear_position == 0:
            # In Park, the vehicle shouldn't move
            self.state.current_speed = 0
            self.state.engine_rpm = 0
        elif self.state.gear_position == 1:
            # In Neutral, the engine should rev but no movement
            self.state.engine_rpm = 800  # RPM is lower in neutral
            self.state.current_speed = 0
        elif self.state.gear_position == 2:
            # In Reverse, set speed and RPM accordingly
            self.state.current_speed = -5  # Reverse speed
            self.state.engine_rpm = 1500
        elif self.state.gear_position == 3:
            # In Drive, update speed normally
            self.state.current_speed = speed
            self.state.engine_rpm = min(8000, max(800, 800 + (speed * 25)))  # Normal RPM behavior

        # Send the updated speed and RPM over CAN
        self.send_speed_and_rpm(self.state.current_speed, self.state.engine_rpm)

    def set_gear_position(self, position):
        # Update the gear position and control the vehicle behavior
        valid_gear_positions = [0, 1, 2, 3]  # 0 -> P, 1 -> N, 2 -> R, 3 -> D
        
        if position not in valid_gear_positions:
            print(f"Invalid gear position: {position}")
            return

        self.state.gear_position = position
        
        # Now, handle the speed and engine behavior based on the gear position
        if self.state.gear_position == 0:  # P (Park)
            self.state.current_speed = 0
            self.state.engine_rpm = 0
        elif self.state.gear_position == 1:  # N (Neutral)
            self.state.engine_rpm = 1000
            self.state.current_speed = 0
        elif self.state.gear_position == 2:  # R (Reverse)
            self.state.current_speed = -5
            self.state.engine_rpm = 2000
        elif self.state.gear_position == 3:  # D (Drive)
            self.state.current_speed = 20
            self.state.engine_rpm = 3000

        # Send the gear position to the CAN bus
        self.send_gear_position(position)

    def send_gear_position(self, position):
        # Send the gear position via CAN
        gear_data = [0] * 8
        if position == 0:
            gear_data[1] = 0  # Park
        elif position == 1:
            gear_data[1] = 1  # Neutral
        elif position == 2:
            gear_data[1] = 2  # Reverse
        elif position == 3:
            gear_data[1] = 3  # Drive
        else:
            print(f"Invalid gear position: {position}")
            return  

        self.send_message(self.gear_id, gear_data)
    
    def toggle_door(self, door_flag):
        # Toggle door lock/unlock
        self.state.door_state ^= door_flag
        door_data = [0] * 8
        door_data[0] = self.state.door_state
        self.send_message(DOOR_ID, door_data)

    def set_signal(self, signal_state):
        # Set turn signal state
        print(f"set_signal called with: {signal_state}")
        self.state.signal_state = signal_state
        
    def set_brake(self, pressed):
        # Set brake status and send CAN message
        self.state.brake_active = pressed
        brake_data = [0] * 8
        if pressed:
            brake_data[7] |= 0x02 
        self.send_message(BRAKE_ID, brake_data)

    def calculate_checksum(self, data):
        # Calculate CAN message checksum
        return sum(data) & 0x0F

    def get_counter(self):
        # Get message counter
        return (int(time.time() * 100)) & 0x0F
    
    # Noise messages to make it harder 
    def _send_noise_message(self):
        noise_id = random.randint(0x100, 0x1FF)  # Random ID range
        noise_data = [random.randint(0, 255) for _ in range(8)]  # Random 8-byte data
        self.send_message(noise_id, noise_data)

    def _monitor_can_messages(self):
        # Monitor incoming CAN messages"""
        while self.state.running:
            if self.can_enabled:
                try:
                    message = self.bus.recv(timeout=0.1)
                    if message:
                        self._process_can_message(message)
                        if self.state.debug_mode:
                            self.last_messages.append(f"ID: {hex(message.arbitration_id)} "
                                                    f"Data: {[hex(x) for x in message.data]}")
                            if len(self.last_messages) > self.max_messages:
                                self.last_messages.pop(0)
                except Exception as e:
                    print(f"Error monitoring CAN messages: {e}")
            time.sleep(0.01)

    def _process_can_message(self, message):
        # Process received CAN message according to DBC specifications
        if len(message.data) < 8:
            print(f"Invalid CAN message length: {len(message.data)}")
            return

        if message.arbitration_id == IGNITION_ID:
            # Extract IgnitionOff
            ignition_off = bool(message.data[2] & 0x40)  # IgnitionOff

            # Determine the new ignition state
            new_ign_state = not ignition_off  

            # Update state if it has changed
            if self.state.ignition_on != new_ign_state:
                print(f"Updating ignition state to: {'ON' if new_ign_state else 'OFF'}")
                self.state.ignition_on = new_ign_state

        elif message.arbitration_id == ENGINE_STATUS_ID:
            if self.state.ignition_on:
                byte_index = 20 // 8
                bit_offset = 20 % 8

                st_eng_run = (message.data[byte_index] >> bit_offset) & 0x03
                self.state.engine_running = (st_eng_run == 2)
            else:
                print('Ignition is OFF')

        elif message.arbitration_id == SPEED_ID:
            # VehicleSpeed
            speed_raw = ((message.data[0] << 4) | (message.data[1] >> 4)) & 0xFFF
            self.state.current_speed = speed_raw * 0.103

        elif message.arbitration_id == RPM_ID:
            # EngineSpeed
            rpm_raw = (message.data[4] << 8) | message.data[5]
            self.state.engine_rpm = rpm_raw * 0.25

        elif message.arbitration_id == TURN_SIGNAL_ID:
            # Process turn signals according to DBC
            left_turn = bool(message.data[0] & 0x10)
            right_turn = bool(message.data[0] & 0x20)  
            signal_active = bool(message.data[1] & 0x01)  
            
            if signal_active:
                self.state.signal_state = (CAN_LEFT_SIGNAL if left_turn else 0) | \
                                              (CAN_RIGHT_SIGNAL if right_turn else 0)
            else:
                self.state.signal_state = 0

        elif message.arbitration_id == BRAKE_ID:
            self.state.brake_active = bool(message.data[7] & 0x02)
            print(self.state.brake_active)

        elif message.arbitration_id == GEAR_ID:
            self.state.gear_position = (message.data[1] & 0x0F) - 4

    def _send_background_messages(self):
        # Send periodic CAN messages based on DBC specifications
        while self.state.running:
            try:
                ignition_data = [0] * 8   
                if self.state.ignition_on:
                    ignition_data[2] = 0x80
                else:
                    ignition_data[2] = 0x40
                ignition_data[4] = self.get_counter() & 0x0F
                ignition_data[4] |= (self.calculate_checksum(ignition_data) << 4)
                self.send_message(self.ignition_id, ignition_data)

                # Engine Status (ID: 0x464)
                engine_data = [0] * 8
                if self.state.engine_running:
                    engine_data[2] |= (2 << 4)
                elif self.state.ignition_on:
                    engine_data[2] |= (1 << 4) 
                else:
                    engine_data[2] &= ~(3 << 4) 
                self.send_message(self.engine_status_id, engine_data)

                # Speed message (ID: 0x1A0)
                speed_data = [0] * 8
                raw_speed = int(self.state.current_speed / 0.103) 
                speed_data[0] = (raw_speed & 0xFF0) >> 4
                speed_data[1] = (raw_speed & 0x00F) << 4
                self.send_message(self.speed_id, speed_data)

                # RPM message (ID: 0x0AA)
                rpm_data = [0] * 8
                rpm_value = int(self.state.engine_rpm / 0.25)  # Scale factor from DBC
                rpm_data[4] = (rpm_value >> 8) & 0xFF
                rpm_data[5] = rpm_value & 0xFF
                self.send_message(self.rpm_id, rpm_data)

                # Turn signal message (ID: 0x1F6)
                signal_data = [0] * 2
                if self.state.signal_state & CAN_LEFT_SIGNAL:
                    signal_data[0] |= 0x10  # LeftTurn bit
                if self.state.signal_state & CAN_RIGHT_SIGNAL:
                    signal_data[0] |= 0x20  # RightTurn bit
                if self.state.signal_state != 0:
                    signal_data[1] |= 0x01  # TurnSignalActive
                self.send_message(self.signal_id, signal_data)

                # Brake status (ID: 0x0A8)
                brake_data = [0] * 8
                if self.state.brake_active:
                    brake_data[7] |= 0x02 
                self.send_message(self.brake_id, brake_data)

                # Gear status (ID:x1D2)
                gear_data = [0] * 8
                gear_data[1] = self.state.gear_position
                self.send_message(self.gear_id, gear_data)

                # Randomly send noise messages
                if random.random() < 0.005:  # 10% chance to send noise
                    self._send_noise_message()

            except Exception as e:
                print(f"Error in background messages: {e}")
                time.sleep(1)

    def cleanup(self):
        # Cleanup CAN connection
        self.state.running = False
        if self.can_enabled:
            self.bus.shutdown()