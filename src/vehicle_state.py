# vehicle_state.py

# CAN Message Flags
CAN_DOOR1_LOCK = 0x01
CAN_DOOR2_LOCK = 0x02
CAN_DOOR3_LOCK = 0x04
CAN_DOOR4_LOCK = 0x08
CAN_LEFT_SIGNAL = 0x10    
CAN_RIGHT_SIGNAL = 0x20   

class VehicleState:
    def __init__(self):
        # Initialize all the state relevant signals
        self.running = True
        self.ignition_on = False
        self.engine_running = False
        self.current_speed = 0
        self.engine_rpm = 0
        self.acceleration = 0
        self.brake_active = False
        self.gear_position = 0
        self.door_state = 0x0F  # All doors locked
        self.signal_state = 0x00
        self.debug_mode = False

    def get_gear_name(self):
        # Map integer gear positions back to readable names
        shift_map = {
            0: "P",  # Park
            1: "N",  # Neutral
            2: "R",  # Reverse
            3: "D",  # Drive
        }
        return shift_map.get(self.gear_position, "Unknown")
