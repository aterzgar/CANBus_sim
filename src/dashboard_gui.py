# dashboard_gui.py

import pygame
import math
import time
import threading
from can_handler import CANHandler
from vehicle_state import (
    VehicleState,
    CAN_DOOR1_LOCK,
    CAN_DOOR2_LOCK,
    CAN_DOOR3_LOCK,
    CAN_DOOR4_LOCK,
    CAN_LEFT_SIGNAL,
    CAN_RIGHT_SIGNAL,
)

class DashboardGUI:
    def __init__(self, can_channel='vcan0'):
        pygame.init()

        # Constants
        self.SCREEN_WIDTH = 1000
        self.SCREEN_HEIGHT = 600
        
        # Colors
        self.BLACK = (0, 0, 0)
        self.WHITE = (255, 255, 255)
        self.RED = (255, 0, 0)
        self.GREEN = (0, 255, 0)
        self.GRAY = (128, 128, 128)
        self.YELLOW = (255, 255, 0)
        
        # Initialize display
        self.screen = pygame.display.set_mode((self.SCREEN_WIDTH, self.SCREEN_HEIGHT))
        pygame.display.set_caption("CAN Bus Simulator")
        
        # Initialize CAN Handler
        self.vehicle_state = VehicleState()
        self.can_handler = CANHandler(can_channel, self.vehicle_state)

        # Dashboard properties
        self.SPEED_CENTER = (self.SCREEN_WIDTH // 4 * 3, self.SCREEN_HEIGHT // 2)
        self.RPM_CENTER = (self.SCREEN_WIDTH // 4, self.SCREEN_HEIGHT // 2)
        self.GAUGE_RADIUS = 120
        self.NEEDLE_LENGTH = 100
        
        # Start monitoring thread
        self.monitor_thread = threading.Thread(target=self.can_handler._monitor_can_messages)
        self.monitor_thread.daemon = True
        self.monitor_thread.start()
    
    def draw_gauge(self, center, radius, min_val, max_val, current_val, title, is_rpm=False):
        # Draw a gauge
        pygame.draw.circle(self.screen, self.WHITE, center, radius, 2)
        
        # Draw markings and numbers
        start_angle = math.pi * 0.75
        end_angle = math.pi * 2.25
        
        if is_rpm:
            steps = 8  
            step_value = 1000
        else:
            steps = 13 
            step_value = 20
        
        for i in range(steps + 1):
            angle = start_angle + (end_angle - start_angle) * (i / steps)
            start_pos = (
                center[0] + (radius - 15) * math.cos(angle),
                center[1] + (radius - 15) * math.sin(angle)
            )
            end_pos = (
                center[0] + radius * math.cos(angle),
                center[1] + radius * math.sin(angle)
            )
            pygame.draw.line(self.screen, self.WHITE, start_pos, end_pos, 2)
            
            value = i * (1 if is_rpm else step_value)
            font = pygame.font.Font(None, 24)
            text = font.render(str(value), True, self.WHITE)
            text_pos = (
                center[0] + (radius - 35) * math.cos(angle) - text.get_width() // 2,
                center[1] + (radius - 35) * math.sin(angle) - text.get_height() // 2
            )
            self.screen.blit(text, text_pos)

        # Draw needle
        current_val = min(max_val, max(min_val, current_val))
        value_ratio = (current_val - min_val) / (max_val - min_val)
        angle = start_angle + (end_angle - start_angle) * value_ratio
        end_pos = (
            center[0] + self.NEEDLE_LENGTH * math.cos(angle),
            center[1] + self.NEEDLE_LENGTH * math.sin(angle)
        )
        pygame.draw.line(self.screen, self.RED, center, end_pos, 3)
        pygame.draw.circle(self.screen, self.RED, center, 5)
        
        # Draw title and value
        font = pygame.font.Font(None, 36)
        title_text = font.render(title, True, self.WHITE)
        title_pos = (center[0] - title_text.get_width() // 2, center[1] + radius + 10)
        self.screen.blit(title_text, title_pos)
        
        if is_rpm:
            value_text = font.render(f"{int(current_val/1000)}k RPM", True, self.WHITE)
        else:
            value_text = font.render(f"{int(current_val)} KPH", True, self.WHITE)
        value_pos = (center[0] - value_text.get_width() // 2, center[1] + 40)
        self.screen.blit(value_text, value_pos)
    
    def draw_status_indicators(self):
        # Draw ignition and engine status indicators
        ignition_rect = pygame.Rect(20, 20, 120, 40)  
        engine_rect = pygame.Rect(20, 70, 120, 40)    
        
        # Ignition status
        if self.vehicle_state.ignition_on:
            ign_color = self.YELLOW
            ign_text = "IGNITION ON"
        else:
            ign_color = self.RED
            ign_text = "IGNITION OFF"
        
        # Engine status
        if self.vehicle_state.engine_running:
            eng_color = self.GREEN
            eng_text = "ENGINE RUN"
        else:
            eng_color = self.RED
            eng_text = "ENGINE OFF"
        
        # Draw indicators with rounded corners
        pygame.draw.rect(self.screen, ign_color, ignition_rect, border_radius=10)
        pygame.draw.rect(self.screen, eng_color, engine_rect, border_radius=10)
        
        # Add text
        font = pygame.font.Font(None, 24)
        
        # Ignition text
        ign_surface = font.render(ign_text, True, self.BLACK)
        ign_text_rect = ign_surface.get_rect(center=ignition_rect.center)
        self.screen.blit(ign_surface, ign_text_rect)
        
        # Engine text
        eng_surface = font.render(eng_text, True, self.BLACK)
        eng_text_rect = eng_surface.get_rect(center=engine_rect.center)
        self.screen.blit(eng_surface, eng_text_rect)

    def draw_brake_status(self):
        # Draw brake status indicator
        brake_rect = pygame.Rect(
            self.SCREEN_WIDTH // 2 - 40,  # x position
            self.SCREEN_HEIGHT - 40,      # y position
            80,                           # width
            30                            # height
        )
        # Only show brake as active if ignition is on and brake is pressed
        if self.vehicle_state.ignition_on and self.vehicle_state.brake_active:
            color = self.RED
        else:
            color = self.GRAY

        pygame.draw.rect(self.screen, color, brake_rect)
        
        # Add text "BRAKE"
        font = pygame.font.Font(None, 30)
        text = font.render("BRAKE", True, self.WHITE)
        text_rect = text.get_rect(center=brake_rect.center)
        self.screen.blit(text, text_rect)

    def draw_door_status(self):
        # Draw the door status indicators
        car_center_x = self.SCREEN_WIDTH // 2
        car_rect = pygame.Rect(
            car_center_x - 55,
            self.SCREEN_HEIGHT - 120,
            110, 
            85
        )
        
        # Draw car body
        pygame.draw.rect(self.screen, self.WHITE, car_rect, 1)
        
        door_state = self.can_handler.state.door_state
        
        # Door dimensions
        door_width = 5
        door_height = 25
        door_offset = 20
        
        # Front left door
        color = self.RED if door_state & CAN_DOOR1_LOCK else self.GREEN
        pygame.draw.rect(self.screen, color, 
                        (car_rect.left - door_width, 
                         car_rect.top + door_offset, 
                         door_width, door_height))
        
        # Front right door
        color = self.RED if door_state & CAN_DOOR2_LOCK else self.GREEN
        pygame.draw.rect(self.screen, color, 
                        (car_rect.right, 
                         car_rect.top + door_offset, 
                         door_width, door_height))
        
        # Rear left door
        color = self.RED if door_state & CAN_DOOR3_LOCK else self.GREEN
        pygame.draw.rect(self.screen, color, 
                        (car_rect.left - door_width, 
                         car_rect.bottom - door_offset - door_height, 
                         door_width, door_height))
        
        # Rear right door
        color = self.RED if door_state & CAN_DOOR4_LOCK else self.GREEN
        pygame.draw.rect(self.screen, color, 
                        (car_rect.right, 
                         car_rect.bottom - door_offset - door_height, 
                         door_width, door_height))

    def draw_turn_signals(self):
        # Draw the turn signal indicators
        self.vehicle_state.signal_state = self.can_handler.state.signal_state
        blink_on = int(time.time() * 2) % 2 == 0
        
        left_x = self.SCREEN_WIDTH // 2 - 100
        right_x = self.SCREEN_WIDTH // 2 + 100
        signal_y = 50
        
        # Left turn signal
        if (self.vehicle_state.signal_state & CAN_LEFT_SIGNAL) and blink_on:
            color = self.GREEN
        else:
            color = self.GRAY
        self.draw_arrow(left_x, signal_y, "left", color)
        
        # Right turn signal
        if (self.vehicle_state.signal_state & CAN_RIGHT_SIGNAL) and blink_on:
            color = self.GREEN
        else:
            color = self.GRAY
        self.draw_arrow(right_x, signal_y, "right", color)

    def draw_arrow(self, x, y, direction, color):
        # Draw a turn signal arrow
        size = 50
        if direction == "left":
            points = [(x + size, y - size//2), (x, y), (x + size, y + size//2)]
        else:
            points = [(x - size, y - size//2), (x, y), (x - size, y + size//2)]
        pygame.draw.polygon(self.screen, color, points)
        pygame.draw.polygon(self.screen, self.WHITE, points, 1)

    def draw_gear_position(self):
        # Display the current shift lever position
        font = pygame.font.Font(None, 48)
        gear_name = self.vehicle_state.get_gear_name()
        gear_text = font.render(f"Gear: {gear_name}", True, self.WHITE)
        gear_pos = (self.SCREEN_WIDTH // 2 - gear_text.get_width() // 2, self.SCREEN_HEIGHT - 150)
        self.screen.blit(gear_text, gear_pos)

    def draw_debug_info(self):
        # Draw debug information
        if not self.vehicle_state.debug_mode:
            return
        
        font = pygame.font.Font(None, 20)
        y = 10
        for msg in self.can_handler.last_messages:
            text = font.render(msg, True, self.YELLOW)
            self.screen.blit(text, (10, y))
            y += 20

    def handle_events(self):
        # Handle pygame events
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.vehicle_state.running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_i:  # 'i' for ignition
                    self.vehicle_state.ignition_on = not self.vehicle_state.ignition_on
                    self.can_handler.set_ignition(self.vehicle_state.ignition_on )
                    if not self.vehicle_state.ignition_on :
                        self.vehicle_state.engine_running = False
                        self.can_handler.set_engine(False)
                        self.vehicle_state.brake_active = False  
                        
                elif event.key == pygame.K_s:  # 's' for start/stop engine
                    if self.vehicle_state.ignition_on : 
                        self.vehicle_state.engine_running = not self.vehicle_state.engine_running
                        self.can_handler.set_engine(self.engine_running)
                        if self.vehicle_state.engine_running:
                            print("Engine started - Ready to drive")
                        else:
                            print("Engine stopped")
                    else:
                        print("Turn ignition on first!")
                
                elif event.key == pygame.K_g:  # 'g' to cycle gear positions
                    gear_order = [0, 1, 2, 3]
                    current_gear = self.vehicle_state.gear_position 
                    if current_gear in gear_order:
                        next_gear = gear_order[(gear_order.index(current_gear) + 1) % len(gear_order)]
                        # Set the next gear position
                        self.vehicle_state.gear_position = next_gear
                        self.can_handler.set_gear_position(next_gear)
                        print(f"Gear changed to: {self.vehicle_state.get_gear_name()}")
                    else:
                        # Handle invalid gear state
                        print(f"Invalid gear position: {current_gear}. Resetting to Park (P).")
                        self.vehicle_state.gear_position = 0
                        self.can_handler.set_gear_position(0)         

                elif event.key == pygame.K_SPACE:  # Brake control
                    if self.vehicle_state.ignition_on:  
                        self.vehicle_state.brake_active = True
                        self.can_handler.set_brake(True)
                        
                elif event.key == pygame.K_UP:
                    if self.vehicle_state.engine_running: 
                        self.vehicle_state.acceleration = 1
                    else:
                        print("Start engine first!")
                        
                elif event.key == pygame.K_DOWN:
                    if self.vehicle_state.engine_running:
                        self.vehicle_state.acceleration = -1
                    else:
                        print("Start engine first!")
                        
                elif event.key == pygame.K_LEFT and self.vehicle_state.ignition_on:  # Only allow signals if ignition is on
                        print("Left key pressed, setting left signal")
                        self.can_handler.set_signal(CAN_LEFT_SIGNAL)
                        
                elif event.key == pygame.K_RIGHT:
                    if self.vehicle_state.ignition_on :  # Only allow signals if ignition is on
                        print("RIGHT key pressed, setting RIGHT signal")
                        self.can_handler.set_signal(CAN_RIGHT_SIGNAL)
                        
                elif event.key == pygame.K_1:
                    self.can_handler.toggle_door(CAN_DOOR1_LOCK)
                    
                elif event.key == pygame.K_2:
                    self.can_handler.toggle_door(CAN_DOOR2_LOCK)
                    
                elif event.key == pygame.K_3:
                    self.can_handler.toggle_door(CAN_DOOR3_LOCK)
                    
                elif event.key == pygame.K_4:
                    self.can_handler.toggle_door(CAN_DOOR4_LOCK)
                    
                elif event.key == pygame.K_d:
                    self.vehicle_state.debug_mode = not self.vehicle_state.debug_mode
                    
            elif event.type == pygame.KEYUP:
                if event.key in (pygame.K_UP, pygame.K_DOWN):
                    self.vehicle_state.acceleration = 0
                    
                elif event.key in (pygame.K_LEFT, pygame.K_RIGHT):
                    if self.vehicle_state.ignition_on :  # Only reset signals if ignition is on
                        self.can_handler.set_signal(0)
                        
                elif event.key == pygame.K_SPACE:  # Brake release
                    if self.vehicle_state.ignition_on :
                        self.vehicle_state.brake_active = False
                        self.can_handler.set_brake(False)

    def run(self):
        """Main loop"""
        try:
            while self.vehicle_state.running:
                self.handle_events()

                # Use centralized state values
                self.ignition_on = self.vehicle_state.ignition_on
                self.engine_running = self.vehicle_state.engine_running
                self.current_speed = self.vehicle_state.current_speed
                self.engine_rpm = self.vehicle_state.engine_rpm
                self.brake_active = self.vehicle_state.brake_active
                self.gear_position = self.vehicle_state.gear_position
                self.signal_state = self.vehicle_state.signal_state

                if self.vehicle_state.engine_running:
                    self.can_handler.update_speed()
                else:
                    self.current_speed = 0
                    self.engine_rpm = 0
                
                # Clear screen
                self.screen.fill(self.BLACK)
                
                # Draw dashboard elements
                self.draw_status_indicators()
                self.draw_gauge(self.RPM_CENTER, self.GAUGE_RADIUS, 0, 8000, 
                            self.engine_rpm, "RPM", True)
                self.draw_gauge(self.SPEED_CENTER, self.GAUGE_RADIUS, 0, 255, 
                            self.current_speed, "Speed")
                self.draw_door_status()
                self.draw_turn_signals()
                self.draw_brake_status()
                self.draw_gear_position() 
                self.draw_debug_info()
                
                # Update display
                pygame.display.flip()
                pygame.time.delay(10)
        finally:
            self.vehicle_state.running = False
            self.can_handler.cleanup()
            pygame.quit()

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--channel', default='vcan0', help='CAN channel')
    args = parser.parse_args()

    dashboard = DashboardGUI(args.channel)
    dashboard.run()