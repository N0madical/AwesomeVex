# ---------------------------------------------------------------------------- #
#                                                                              #
# 	Module:       main.py                                                      #
# 	Author:       Trevor Wohlers and Aiden Cunningham                          #
# 	Created:      10/30/2024, 10:57:00 AM                                      #
# 	Description:  V5 project                                                   #
#                                                                              #
# ---------------------------------------------------------------------------- #

# Library imports
from vex import (Brain, Controller, Inertial, Ports, Sonar, Motor, FORWARD, PERCENT, REVERSE, DEGREES, RotationUnits, Timer, Line, MM, Triport, XAXIS, YAXIS)
from vex import *
import math

brain = Brain()
controller = Controller()

prevSystemTime = brain.timer.system_high_res()
systemTime = prevSystemTime + 1
dt = lambda : systemTime - prevSystemTime

class States:
    """List of states."""
    DEFAULT = "DEFAULT"     # There must be a better way to do this, 
    # MOUNDDIST = "WAITING FOR LEFT MOUND"
    # AWAITMOUND = "AWAITING MOUND"
    # AWAITWALL = "AWAITING WALL"
    # REORIENT = "REORIENTING"
    # RETURNTOSTART = "Returning :)"
    WALL_FOLLOWING = "Following Wall"
    TURNING = "Turning"
class Modes:
    """List of Modes."""
    NAVIGATE = "NAVIGATE"
    DEFAULT = "DEFAULT"
    TELEOP = "TELEOP" # but this was the best way I could find to make the states indexable with 'States.*' and be reversible back to the state name.
    FRUITFOLLOWING = "Fruit Following"
    CALIBRATE = "Calibrating Gyro"
    COLLECTION = "Collecting Fruit"

currentState = States.DEFAULT
"""Current system state. Default is IDLE."""
currentMode = Modes.DEFAULT
newState = None
"""state to change to on the next cycle"""
returnState = None
returnMode = None
# moundDist = 0 # used only for lab 2? 3? navigation

cameraConfig = {
  "brightness": 60,
  "signatures": [
    {
      "name": "SIG_1",
      "parameters": {
        "uMin": -4941,
        "uMax": -3581,
        "uMean": -4261,
        "vMin": -3543,
        "vMax": -2871,
        "vMean": -3207,
        "rgb": 3097909,
        "type": 0,
        "name": "SIG_1"
      },
      "range": 5.4
    },
    {
      "name": "SIG_2",
      "parameters": {
        "uMin": 6697,
        "uMax": 7791,
        "uMean": 7244,
        "vMin": -2431,
        "vMax": -2123,
        "vMean": -2277,
        "rgb": 12939350,
        "type": 0,
        "name": "SIG_2"
      },
      "range": 5.8
    },
    {
      "name": "SIG_3",
      "parameters": {
        "uMin": 2379,
        "uMax": 3059,
        "uMean": 2719,
        "vMin": -3455,
        "vMax": -3149,
        "vMean": -3302,
        "rgb": 10847840,
        "type": 0,
        "name": "SIG_3"
      },
      "range": 4.6
    },
    {
      "name": "SIG_4",
      "parameters": {
        "uMin": 6523,
        "uMax": 7249,
        "uMean": 6886,
        "vMin": 451,
        "vMax": 811,
        "vMean": 631,
        "rgb": 10902628,
        "type": 0,
        "name": "SIG_4"
      },
      "range": 4.2
    },
    {
      "name": "SIG_5",
      "parameters": {
        "uMin": 0,
        "uMax": 0,
        "uMean": 0,
        "vMin": 0,
        "vMax": 0,
        "vMean": 0,
        "rgb": 0,
        "type": 0,
        "name": "SIG_5"
      },
      "range": 2.5
    },
    {
      "name": "SIG_6",
      "parameters": {
        "uMin": 0,
        "uMax": 0,
        "uMean": 0,
        "vMin": 0,
        "vMax": 0,
        "vMean": 0,
        "rgb": 0,
        "type": 0,
        "name": "SIG_6"
      },
      "range": 2.5
    },
    {
      "name": "SIG_7",
      "parameters": {
        "uMin": 0,
        "uMax": 0,
        "uMean": 0,
        "vMin": 0,
        "vMax": 0,
        "vMean": 0,
        "rgb": 0,
        "type": 0,
        "name": "SIG_7"
      },
      "range": 2.5
    }
  ],
  "codes": []
}

sigList : list[Signature] = []
sigDataOrder = ["uMin", "uMax", "uMean", "vMin", "vMax", "vMean"]
print("Vision Definition Data")
for i in range(len(cameraConfig["signatures"])): 
    sig = cameraConfig["signatures"][i]
    sigData : list[int] = [i+1]
    sigData.extend([sig["parameters"][k] for k in sigDataOrder])
    sigData.append(sig["range"])
    sigData.append(sig["parameters"]["type"])
    print(sigData)
    sigList.append(Signature(*sigData))

class Drivetrain:
    def __init__(self, gyro : Inertial):
        # self.gyro = gyro
        self.gyroHeading = lambda : gyro.heading()*(math.pi/180) # lambda is not needed but is more convenient
        self.prevGyroHeading = self.gyroHeading()
        self.prevTime = brain.timer.system()
        """gyro position in radians"""
        self.driving = False
        self.active = False
        """Reset every cycle. Used to automatically stop motors when not recieving input. \n
        Drivetrain.driving should be used to determine if the drivetrain is in active use."""
        self.robotPos : tuple[float, float] = (0,0)
        """coordinate position of the robot relative to the starting point"""
        self.gyroVel : tuple[float, float] = (0,0)
        """velocity estimate from integrating accelerometer"""
        self.allowMovementAxis = [True, True, True]

    def stopAll(self):
        """Stops all drivetrain motors and resets Drivetrain.driving to False."""
        robot.motor_FL.stop()
        robot.motor_FR.stop()
        robot.motor_BL.stop()
        robot.motor_BR.stop()
        self.driving = False

    def drive(self, xVel : float, yVel : float, rotVel : float, robotRelative = False):
        """Velocities are percentages with valid range -100 to 100. \n
        linearMode=0 for field relative; linearMode=1 for robot relative. \n
        +x is forward. \n
        The drivetrain will automatically stop itself if this method is not called each cycle."""
        # self.gyroHeading = ((gyro.rotation()%360)*(math.pi/180)) # alternative to using predefined lambda for gyro rotation

        self.active = True

        driveHeading = math.atan2(yVel,xVel)%(math.pi*2)
        """field relative angle to drive in"""
        
        driveAngle = -driveHeading # default value while in robotRelative mode
        """angle to drive in relative to the robot's heading"""
        
        if not robotRelative:
            driveAngle = (self.gyroHeading()-driveHeading)%(2*math.pi)

        driveVel = math.sqrt((xVel**2) + (yVel**2))

        vFL = (math.cos(driveAngle+(math.pi/4)) * driveVel) + rotVel
        vFR = (math.sin(driveAngle+(math.pi/4)) * driveVel) - rotVel
        vBL = (math.sin(driveAngle+(math.pi/4)) * driveVel) + rotVel
        vBR = (math.cos(driveAngle+(math.pi/4)) * driveVel) - rotVel
        
        # prevent any motor from driving at more than 100%
        maxV = max(abs(vFL), abs(vFR), abs(vBL), abs(vBR))
        if maxV > 100:
            scale = 100 / maxV
        else:
            scale = 1

        # run motors

        # Printer.add((str(vFL) + ", " + str(vFR) + ", " + str(vBL) + ", " + str(vBR)), 5)

        if(driveVel > 1 or abs(rotVel) > 1):
            robot.motor_FL.spin(FORWARD, vFL*scale, PERCENT)
            robot.motor_FR.spin(FORWARD, vFR*scale, PERCENT)
            robot.motor_BL.spin(FORWARD, vBL*scale, PERCENT)
            robot.motor_BR.spin(FORWARD, vBR*scale, PERCENT)
            self.driving = True
        else:
            self.stopAll()

    def updateOdometry(self):
        """Updates the robot position. """
        self.gyroVel = (self.gyroVel[0] + gyro.acceleration(XAXIS) / 9.8 * dt()/1000000, self.gyroVel[1] + gyro.acceleration(YAXIS) / 9.8 * dt()/1000000)
        self.robotPos = (self.robotPos[0] + self.gyroVel[0] * dt()/1000000, self.robotPos[1] + self.gyroVel[1] * dt()/1000000)

class Arm:
    def __init__(self, liftGroup : MotorGroup, gripper : Motor) -> None:
        liftGroup.set_stopping(HOLD)
        self.liftGroup = liftGroup
        gripper.set_stopping(HOLD)
        # gripper.set_max_torque(1, TorqueUnits.NM)
        self.gripper = gripper
        self.gripperStatus : int = 2
        """1 => open, -1 => closed, 0 => moving, 2 => undefined"""
        self.gripperCommand = 0
        """1 => open, -1 => closed, 0 => no command"""
        self.gripperCommandTimer = 0
        self.driving = False
        self.active = False
        """Reset every cycle. Used to automatically stop motors when not recieving input. \n
        Drivetrain.driving should be used to determine if the drivetrain is in active use."""

    def lift(self, velocity):
        self.active = True
        #if velocity > 1:
        self.driving = True
        self.liftGroup.spin(FORWARD, velocity, RPM)
    def stop(self):
        self.liftGroup.stop()
        self.driving = False
    
    def open(self):
        self.gripperCommand = 1
        self.gripperCommandTimer = 0
    def close(self):
        self.gripperCommand = -1
        self.gripperCommandTimer = 0
    def updateGripper(self):
        if self.gripperCommand == self.gripperStatus:
            self.gripperCommand = 0
        if self.gripperCommand != 0:
            self.gripperCommandTimer += dt()
            #self.gripper.spin_for(FORWARD, 1, TimeUnits.SECONDS, 50, PERCENT)
            self.gripper.spin(FORWARD, self.gripperCommand * 50, RPM)
            if self.gripperStatus != 0 and abs(self.gripper.velocity(RPM)) > 20 and self.gripperCommandTimer > 250000: # reach a minimun speed, 0.1 second minimum time
                self.gripperStatus = 0
        if self.gripperStatus == 0 and abs(self.gripper.velocity(RPM)) < 5 and self.gripperCommandTimer > 500000: # check for stopped
            self.gripper.stop()
            self.gripperStatus = self.gripperCommand
            self.gripperCommand = 0
        # if self.gripper.current() > 0.5 and abs(self.gripper.velocity()) < 1: # safety in case the rest of the code breaks
        #     self.gripper.stop()
        #     self.gripperCommand = 0
        #     self.gripperStatus = 2
        if self.gripperCommandTimer > 1500000: # 1.5 sec timeout
            self.gripperCommand = 0
            self.gripper.stop()
            self.gripperStatus = 2
        if self.gripperCommand == 0:
            self.gripper.stop()
        
class Robot:
    def __init__(self, PortMotorFL, PortMotorFR, PortMotorBL, PortMotorBR, PortMotorTRAY, PortGyro, PortVision, PortArmL, PortArmR, PortGripper, PortSonarB : Triport.TriportPort, PortSonarR : Triport.TriportPort):
        """initializes the hardware components of the robot"""
        self.motor_FL = Motor(PortMotorFL)
        self.motor_FR = Motor(PortMotorFR)
        self.motor_BL = Motor(PortMotorBL)
        self.motor_BR = Motor(PortMotorBR)
        self.motor_TRAY = Motor(PortMotorTRAY)
        self.motor_FL.set_reversed(True)
        self.motor_BL.set_reversed(True)
        self.gyro = Inertial(PortGyro)

        self.trayState = 0
        self.navHeadingSetpoint = 0
        # self.hold = False
        
        gyroPos1 = 0
        gyroPos2 = 1
        while abs(gyroPos1 - gyroPos2) > 0.2:
            print("attempting gyro calibration")
            self.gyro.calibrate()
            while(self.gyro.is_calibrating()):
                sleep(10)
            self.gyro.reset_rotation()
            gyroPos1 = self.gyro.heading()
            sleep(2000)
            gyroPos2 = self.gyro.heading()
        
        self.gyro.reset_rotation()
        self.sonarR = Sonar(PortSonarR) # uses 3wire a/b pair, so set to use a (first port of pair)
        self.sonarB = Sonar(PortSonarB)
        self.drivetrain = Drivetrain(self.gyro)
        self.vision = Vision(PortVision, cameraConfig["brightness"], *sigList)
        self.camera = Camera()

        # lineL = Line(brain.three_wire_port.e)
        # lineR = Line(brain.three_wire_port.f)

        # arm
        motorArmL = Motor(PortArmL, GearSetting.RATIO_18_1)
        motorArmR = Motor(PortArmR, GearSetting.RATIO_18_1)
        motorArmR.set_reversed(True)
        motorGroupArm = MotorGroup(motorArmL, motorArmR)
        motorGripper = Motor(PortGripper, GearSetting.RATIO_18_1)
        self.arm = Arm(motorGroupArm, motorGripper)

    def toggleTray(self):
        """Moves the fruit tray up and down"""
        if self.trayState == 0:
            self.motor_TRAY.spin_to_position(360, DEGREES, False)
            self.trayState = 1
        else:
            self.motor_TRAY.spin_to_position(0, DEGREES, False)
            self.trayState = 0

# ports as ints are 0 indexed, but are 1 indexed on the brain and using 'Ports.Port_' notation
robot = Robot(0, 1, 2, 3, 9, 8, 20, 5, 6, 19, brain.three_wire_port.c, brain.three_wire_port.a) # TODO: fix gripper port number
"""container for all robot hardware objects"""

gyro = robot.gyro
sonarR = robot.sonarR
sonarB = robot.sonarB
drivetrain = robot.drivetrain
vision = robot.vision
camera = robot.camera
arm = robot.arm

class Buttons:
    A = 0
    B = 1
    X = 2
    Y = 3
    UP = 4
    DOWN = 5
    LEFT = 6
    RIGHT = 7
    L1 = 8
    L2 = 9
    R1 = 10
    R2 = 11
    
    class ControllerButtonTracker:
        """Button tracking class. \n 
        Uses 0 indexed list of buttons ordered: A, B, X, Y, ^, v, <, >, L1, L2, R1, R2"""
        def __init__(self, controller : Controller) -> None:
            self.controller = controller
            self.getNewButtonlist = lambda : [self.controller.buttonA.pressing(), self.controller.buttonB.pressing(), 
                                        self.controller.buttonX.pressing(), self.controller.buttonY.pressing(),
                                        self.controller.buttonUp.pressing(),self.controller.buttonDown.pressing(),
                                        self.controller.buttonLeft.pressing(), self.controller.buttonRight.pressing(),
                                        self.controller.buttonL1.pressing(), self.controller.buttonL2.pressing(),
                                        self.controller.buttonR1.pressing(), self.controller.buttonR2.pressing()]
            self.prevButtonList = self.getNewButtonlist()
            self.buttonList = self.getNewButtonlist()
        def pressing(self, button):
            """Returns whether the selected button is currently pressed down. """
            return self.buttonList[button]
        def pressed(self, button):
            """Returns whether the selected button was pressed since the last cycle. \n
            WARNING: may still activiate multiple times on press due to button bounce"""
            return self.pressedButtons[button]
        def released(self, button):
            """Returns whether the selected button was released since the last cycle."""
            return self.releasedButtons[button]
        def update(self):
            self.prevButtonList = self.buttonList
            self.buttonList = self.getNewButtonlist()
            self.pressedButtons = [self.buttonList[i] and not self.prevButtonList[i] for i in range(12)]
            self.releasedButtons = [not self.buttonList[i] and self.prevButtonList[i] for i in range(12)]

controllerButtons = Buttons.ControllerButtonTracker(controller)

class Printer:
    
    brainList : list[str] = ["","","","","","","","","",""]
    controllerList : list[str] = ["","",""]
    
    @classmethod
    def addGyro(cls, location : int, index):
        """adds the gyro heading to the print list"""
        # cls.brainList[index] = (("Gryo: " + str(robot.gyro.heading())))

        Printer.add("Gryo: " + str(robot.gyro.heading()), location, index)
    
    @classmethod
    def addSonar(cls, location : int, index):
        """adds the sonar values (front, left) to the print list"""
        #cls.brainList[index] = (("SF:" + str(sonarF.distance(MM)) + ", SL:" + str(robot.sonarL.distance(MM))))
        Printer.add(("SB:" + str(sonarB.distance(MM)) + ", SR:" + str(robot.sonarR.distance(MM))), location, index)
    
    @classmethod
    def add(cls, s : str, location : int, index : int):
        """
        Adds str to be printed at index \n
        Brain Indexes: 0-8
        """
        if location == 0:
            cls.brainList[index] = (s)
        elif location == 1:
            cls.controllerList[index] = (s)
        #else:

    @classmethod
    def print(cls):
        """Prints the contents of the print list to the brain"""
        # brain.screen.clear_screen()
        l = 1
        for s in cls.brainList:
            brain.screen.set_cursor(l,1)
            brain.screen.print(s, "                                     ")
            l += 1
        l = 1
        for s in cls.controllerList:
            controller.screen.set_cursor(l,1)
            controller.screen.print(s, "                                     ")
            l += 1

class Delays:
    class Delay:
        def __init__(self, delay, delayedState):
            self.delay = delay
            self.delayedState = delayedState
            self.startTime = systemTime
        def check(self):
            global newState
            if systemTime - self.startTime > self.delay * 1000000:
                newState = self.delayedState
                return True
            return False

    scheduledDelays : list[Delay] = []
    
    @classmethod
    def schedule(cls, delay : Delay):
        if not delay.delayedState in [d.delayedState for d in cls.scheduledDelays]:
            cls.scheduledDelays.append(delay)
    @classmethod
    def checkAllDelays(cls):
        for d in cls.scheduledDelays:
            if d.check():
                cls.scheduledDelays.remove(d)

class PID:
    """Standard PID controller"""
    def __init__(self, kP : float = 0, kI : float = 0, kD : float = 0, maxOut = None, inputSupplier : Callable[[], float | int] | None = None, continuousRotation : bool = False, invertInput : bool = False, angleUnits = RotationUnits.DEG):
        """Creates a new PID controller. \n
           An inputSupplier may be supplied to automatically read the input value when the PID controller is updated. \n
           The inputSupplier should be formatted as 'lambda : inputValue'"""
        global PIDcontrollers
        self.kP = kP
        self.kI = kI
        self.kD = kD
        self.prevError = 0
        self.output = 0
        self.setpoint = 0
        self.maxOut = maxOut
        self.inputSupplier = inputSupplier
        self.integrator = 0
        self.continuousRotation = continuousRotation
        self.angleUnits = angleUnits
        PIDcontrollers.append(self)
        self.invertInput = invertInput
    def reset(self, resetSetpoint : bool = False):
        """Resets the PID controller to its initial state. ***DOES NOT RESET SETPOINT BY DEFAULT"""
        self.prevError = 0
        self.output = 0
        self.integrator = 0
        if resetSetpoint:
            self.setpoint = 0
    def update(self, input = None):
        """Updates the output value of the PID controller. This should be run once per cycle. \n
           Returns the PID instance, which may be used for method chaining."""
        # allows use of predefined inputSupplier
        if input == None and self.inputSupplier != None: # if no input, use supplier
            input = self.inputSupplier()
        if input == None:                                # if no supplier and no input, raise an error
            raise RuntimeError("No input value given.")
        
        # calculate error
        if self.continuousRotation == False: # standard PID
            error = self.setpoint - input
        else:                                # continuous rotation PID
            if self.angleUnits == RotationUnits.DEG:
                error = ((self.setpoint - input) + 180) % 360 - 180
            elif self.angleUnits == RotationUnits.REV:
                error = ((self.setpoint - input) + 0.5) % 1 - 0.5
            else: # use RAW for radians
                error = ((self.setpoint - input) + math.pi) % (2*math.pi) - math.pi
        
        if self.invertInput:
            error = -error

        self.integrator += error * dt() / 1000000.0
        
        # calculate new output
        self.output = (self.kP * error) + (self.kI * self.integrator) + (self.kD * (error - self.prevError) / dt())
        self.prevError = error
        
        # clamp output if requested
        if self.maxOut != None:
            if self.output > self.maxOut:
                self.output = self.maxOut
            elif self.output < -self.maxOut:
                self.output = -self.maxOut
        
        # returns the PID instance
        # return self
    def setNewSetpoint(self, setpoint  : float):
        """Sets a new setpoint"""
        if self.continuousRotation == False: # standard PID
            self.setpoint = setpoint
        else:                                # continuous rotation PID
            if self.angleUnits == RotationUnits.DEG:
                self.setpoint = ((setpoint) + 3*180) % 360 - 180
            elif self.angleUnits == RotationUnits.REV:
                self.setpoint = ((setpoint) + 3*0.5) % 1 - 0.5
            else: # use RAW for radians
                self.setpoint = ((setpoint) + 3*math.pi) % (2*math.pi) - math.pi
        return self
    def getOutput(self):
        """Returns the output value of the PID controller. This value may be sent dirrectly to motors, etc. \n
           May be called on the return value of PID.update()"""
        return self.output
    def unbind(self):
        """Unbinds this instance from the auto update list. Returns this instance. Use bind() to reverse this action."""
        PIDcontrollers.remove(self)
        return self
    def bind(self):
        """Binds this instance to the auto update list. Returns this instance. Use unbind() to reverse this action."""
        PIDcontrollers.append(self)
        return self
    def isAutoUpdate(self):
        """Returns whether this PID instance is bound to the auto update list"""
        return self in PIDcontrollers   
    def atSetpoint(self, tolerance = 5, input = None):
        if input == None and self.inputSupplier != None:
            input = self.inputSupplier()
        if input == None:
            raise RuntimeError("No input value given.")
        if self.continuousRotation == False: # standard PID
            error = self.setpoint - input
        else:                                # continuous rotation PID
            if self.angleUnits == RotationUnits.DEG:
                error = ((self.setpoint - input) + 180) % 360 - 180
            elif self.angleUnits == RotationUnits.REV:
                error = ((self.setpoint - input) + 0.5) % 1 - 0.5
            else: # use RAW for radians
                error = ((self.setpoint - input) + math.pi) % (2*math.pi) - math.pi
        return abs(error) < tolerance
    @classmethod
    def updateAllPIDs(cls):
        for pid in PIDcontrollers:
            pid.update()

PIDcontrollers : list[PID] = []
"""List of all active PID controllers"""

turnPID = PID(5, 0, 0, 100, gyro.heading, True, angleUnits=RotationUnits.DEG)
"""Turn handler"""

fruitTurnPID = PID(1,0,1, 100, None, False, invertInput=True)
"""PID to use vision object pixel position to turn the robot. \n
Similar behavior may be achieved by scaling the pixel value to degrees from center, then using the turnPID. turnPID would have to be unbound from auto update for turnPID to work correctly for this behavior."""
fruitTurnPID.unbind() # prevent the state machine from automatically updating this PID. An input supplier must be given for auto update to work
fruitTurnPID.setNewSetpoint(160)

fruitDistPID = PID(5,0,1, 100, None, False)
fruitDistPID.unbind()
fruitDistPID.setNewSetpoint(35)

wallPID = PID(1, 0, 1, 150, lambda : sonarB.distance(MM), False, False)
wallPID.setNewSetpoint(200)

class LocatedVisionObject:
    """Custom class for vision objects. The VEX default uses pixel positions. This does the math to get distance and relative height in cm."""
    def __init__(self, dist : float, height : float, angleTo : float, color : int, fruitType : int) -> None:
        """default constructor - not intended for general use. Use LocatedVisionObject.fromRaw() instead."""
        self.dist = dist
        """striaght line distance to fruit (not horizontal distance)"""
        self.height = height
        """height of fruit from ground in mm"""
        self.angleTo = angleTo
        """horizontal angle to the fruit in degrees (right of center positive)"""
        self.color = color
        """integer representing the signature used to find the fruit"""
        self.fruitType = fruitType
        """0 for small fruit, 1 for large fruit"""
    @classmethod
    def fromRaw(cls, color : int, object : VisionObject):
        """takes in data from a VEX standard VisionObject and converts the pixel values into actual distances in cm."""
        if object.width/object.height > 0.9:
            fruitRadius = 4.45 # radius in cm
            fruitType = 1      # wide fruit
        else:
            fruitRadius = 2.86 # radius in cm
            fruitType = 0      # narrow fruit
        halfAngleRadians = 0.00337 * object.width / 2 + 0.01 # +0.01 is a minor correction to improve distance accuracy
        dist = fruitRadius/math.sin(halfAngleRadians)
        return LocatedVisionObject(dist, 
                                   math.sin((137-object.centerY) * 0.00337) * dist, # (106-object.centerY) * 0.00337); 106 is the center, 137 corrects the angle of the camera
                                   ((object.centerX - 158) * 0.19), 
                                   color, fruitType) 
    def __str__(self) -> str:
        return "Dist:"+str(self.dist)+", Height:"+str(self.height)+", Angle:"+str(self.angleTo)+", Type:"+str(self.fruitType)+", Color:"+str(self.color)

class Camera:
    """Class to handle robot vision"""

    def __init__(self):
        self.visionResults : list[list[VisionObject]] = [[],[],[],[],[],[],[]]
        """2d array containing all of the vision objects the sensor found this cycle"""
        self.largestObject = None
        """the largest object the vision sensor saw this cycle"""
        self.largestVisionObjectType = 0
        """the (0 indexed) id of the signature of the largest object found this cycle"""

        self.locatedVisionObjects : list[LocatedVisionObject] = []
        """visionResults list converted to a single list of LocatedVisionObject"""
        self.averageLargestObject : LocatedVisionObject | None = None
        """largest vision object averaged over 50 cycles"""
        self.pastLargestLocatedObjects : list[LocatedVisionObject] = []
        self.noDetectCounter = 0
        """cycles since vision object was detected"""

        self.vision = robot.vision
        self.take_snapshot = self.vision.take_snapshot
        self.largest_object = self.vision.largest_object
    
    def update(self):
        """updates all information related to vision"""
        self.largestObject
        self.largestVisionObjectType
        self.visionResults
        self.noDetectCounter
        self.averageLargestObject
        self.largestObject = None
        for sig in range (len(sigList)):
            minArea = 50 # minimum allowable VisionObject area; smaller is ignored
            sigResults = self.take_snapshot(sigList[sig])
            self.visionResults[sig] = []

            if sigResults != None:
                self.visionResults[sig] = [i for i in sigResults if (i.height*i.width) > minArea] # only allow objects larger than minArea
                if largestVisionObject == None:                                    # there is not largest yet
                    largestVisionObject = vision.largest_object()
                    largestVisionObjectType = sig
                elif vision.largest_object().height > largestVisionObject.height:  # the new largest is larger than the old largest
                    largestVisionObject = vision.largest_object()
                    largestVisionObjectType = sig
                if largestVisionObject.height*largestVisionObject.width < minArea: # largest is still too small
                    largestVisionObject = None

        # located objects
        locatedVisionObjects = []
        for i in range(3): # don't need to locate anything except the fruits
            for object in self.visionResults[i]:
                locatedVisionObjects.append(LocatedVisionObject.fromRaw(sig, object))
        
        # moving average largest object
        if largestVisionObject != None: # if an object exists
            self.noDetectCounter = 0
            if len(self.pastLargestLocatedObjects) != 0: # if has contents, insert the new largest
                self.pastLargestLocatedObjects.insert(0, LocatedVisionObject.fromRaw(largestVisionObjectType, largestVisionObject))
                if len(self.pastLargestLocatedObjects) > 50: # if too many, remove last
                    self.pastLargestLocatedObjects.pop()
            else: # if list is empty, simply add new largest
                self.pastLargestLocatedObjects.append(LocatedVisionObject.fromRaw(largestVisionObjectType, largestVisionObject))
            
            # calculate the average
            n = len(self.pastLargestLocatedObjects) 
            self.averageLargestObject = LocatedVisionObject(sum([i.dist for i in self.pastLargestLocatedObjects])/n,
                                                        sum([i.height for i in self.pastLargestLocatedObjects])/n,
                                                        sum([i.angleTo for i in self.pastLargestLocatedObjects])/n,
                                                        self.pastLargestLocatedObjects[0].color,
                                                        self.pastLargestLocatedObjects[0].fruitType)
        else: # no object
            if self.noDetectCounter > 1000000: # 1 second passed with no object : no more averaging
                self.pastLargestLocatedObjects.clear()
                self.averageLargestObject = None
            else:                         # 1 second not yet passed : count time since last detection
                self.noDetectCounter += dt()


times = []
timeUsage = []

def timer():
    times.append(brain.timer.system_high_res())

def timeUsageCalc():
    timeUsage.clear()
    for i in range(len(times)-1):
        timeUsage.append(times[i+1]-times[i])

def globalPrinter():
    """Method to print in another thread. Always use this to print everything."""
    while True:
        print("DT:", str(dt()))
        print("Heading:", gyro.heading())
        
        cameraObject = camera.largestObject # store the value to prevent the main thread from updating the value from a VisionObject to None between the if and the print
        if cameraObject != None:
            print("Largest:", cameraObject.centerX, cameraObject.centerY, cameraObject.width, cameraObject.height)
        else:
            print("No object detected this cycle")
            
        averagedVisionObject = camera.averageLargestObject
        if averagedVisionObject != None:
            print(averagedVisionObject)
        else : print("No object detected")

        print(camera.visionResults)
        print("SB:" + str(sonarB.distance(MM)) + ", SR:" + str(sonarR.distance(MM)))

        Printer.add((str(currentMode) + ", " + str(currentState)), 0, 4)
        Printer.add((str(currentMode) + ", " + str(currentState)), 1, 0)
        Printer.add(("Stat:"+str(arm.gripperStatus) + " Com:"+str(arm.gripperCommand)), 1, 1)
        Printer.add((str(arm.gripper.current())), 1, 2)
        Printer.addSonar(0,1)
        Printer.addGyro(0,2)
        Printer.add("DT:" + str(dt()), 0, 3)
        Printer.add("Pos: (" + str(drivetrain.robotPos[0])+", "+str(drivetrain.robotPos[1])+")", 0, 6)

        Printer.print()
        printThread.sleep_for(50)
        print("setpoint:", wallPID.setpoint)
        
printThread = Thread(globalPrinter)

def stateMachine():
    """Run the state machine. \n
       Parameter controls whether to update all PIDs at the start of the cycle. \n
       Probably best to leave updatePIDs False without a good reason to change it."""
    global currentMode
    global currentState
    global PIDcontrollers
    #global moundDist

    # this may be used to update every PID controller if they are configured with input suppliers
    # if a PID controller is not configured with a lambda-based input supplier, update it within the appropriate state instead

    global newState

    if controllerButtons.pressed(Buttons.B): # exit button
        newState = States.DEFAULT
        currentMode = Modes.DEFAULT

    if newState != None and newState != currentState:
        currentState = newState

    newState = None

    if currentMode == Modes.DEFAULT:
        newState = States.DEFAULT

        if controllerButtons.pressed(Buttons.A): # end condition 
            currentMode = Modes.TELEOP   # end behavior (state change + additional behaviors)

        # if controllerButtons.pressed(Buttons.X): # end condition 
        #     currentMode = Modes.NAVIGATE   # end behavior (state change + additional behaviors)
        #     newState = States.MOUNDDIST
        #     robot.navHeadingSetpoint = 0
        #     moundDist = 925
        #     robot.hold = False

        # if controllerButtons.pressed(Buttons.Y): # end condition
        #     currentMode = Modes.NAVIGATE   # end behavior (state change + additional behaviors)
        #     newState = States.MOUNDDIST
        #     robot.navHeadingSetpoint = 0
        #     moundDist = 725
        #     robot.hold = False

        if controllerButtons.pressed(Buttons.X):
            currentMode = Modes.COLLECTION

        if controllerButtons.pressed(Buttons.L2):
            currentMode = Modes.FRUITFOLLOWING

    elif currentMode == Modes.TELEOP:
        # do
        
        turnPID.setpoint += controller.axis1.position() * .25 * dt()/1000000
        drivetrain.drive(controller.axis3.position(), controller.axis4.position(), turnPID.getOutput(), controllerButtons.pressing(Buttons.L1))

        if controllerButtons.pressing(Buttons.L1):
            arm.lift(20)
        if controllerButtons.pressing(Buttons.L2):
            arm.lift(-20)
        if controllerButtons.pressed(Buttons.R1):
            arm.open()
        if controllerButtons.pressed(Buttons.R2):
            arm.close()

        if controllerButtons.pressed(Buttons.UP) or controllerButtons.pressed(Buttons.DOWN):
            robot.toggleTray()
        #end
        if controllerButtons.pressed(Buttons.A):
            currentMode = Modes.DEFAULT
            newState = States.DEFAULT

    # elif currentMode == Modes.NAVIGATE:

    #     if currentState == States.DEFAULT:
    #         drivetrain.drive(0, 0, turnPID.getOutput(), False)
    #     # else:
    #     #     driveSpeed = 100
    #     turnPID.setNewSetpoint(robot.navHeadingSetpoint)
    #     #     drivetrain.drive(driveSpeed*math.cos(robot.navHeadingSetpoint), driveSpeed*math.sin(robot.navHeadingSetpoint), turnPID.getOutput(), True)
    #     #     Printer.add(str(robot.navHeadingSetpoint), 5)
        
    #     if currentState == States.MOUNDDIST:
    #         drivetrain.drive(100, 0, turnPID.getOutput(), False)
    #         if (sonarL.distance(MM) > moundDist-25 and sonarL.distance(MM) < moundDist+25) and (robot.hold == False):
    #             robot.navHeadingSetpoint = 270
    #             robot.hold = True
    #             Delays.schedule(Delays.Delay(1.9, States.AWAITWALL))

    #         # if (sonarF.distance(MM) < 1250):
    #         #     robot.navHeadingSetpoint = (robot.navHeadingSetpoint - 90) % 360
    #         #     newState = States.AWAITWALL

    #     elif currentState == States.AWAITWALL:
    #         robot.hold = False
    #         drivetrain.drive(0, -100, turnPID.getOutput(), False)
    #         if(sonarF.distance(MM) < 300 and turnPID.atSetpoint(5)):
    #             robot.navHeadingSetpoint = 180
    #             newState = States.REORIENT
        
    #     # elif currentState == States.AWAITMOUND:
    #     #     if (sonarF.distance(MM) < 100):
    #     #         Delays.schedule(Delays.Delay(3, States.AWAITWALL))
        
    #     elif currentState == States.REORIENT:
    #         drivetrain.drive(-100, 0, turnPID.getOutput(), False)
    #         if(sonarF.distance(MM) < 300 and turnPID.atSetpoint(5)):
    #             newState = States.RETURNTOSTART

    #     elif currentState == States.RETURNTOSTART:
    #         drivetrain.drive(0, 100, turnPID.getOutput(), False)
    #         robot.navHeadingSetpoint = 90
    #         if(sonarF.distance(MM) < 235):
    #             robot.navHeadingSetpoint = 0
    #             newState = States.DEFAULT
        
    #     if controllerButtons.pressed(Buttons.B): # end condition 
    #             newState = States.DEFAULT
    #             currentMode = Modes.DEFAULT

    elif currentMode == Modes.FRUITFOLLOWING:
        if camera.largestObject != None:
            #drivetrain.drive(fruitDistPID.update(largestVisionObject.height).getOutput(), 0, fruitTurnPID.update(largestVisionObject.centerX).getOutput(), True)
            pass
        else:
            drivetrain.stopAll()
        if controllerButtons.pressed(Buttons.L2):
            currentMode = Modes.DEFAULT

    elif currentMode == Modes.COLLECTION:
        
        if controllerButtons.pressed(Buttons.X):
            currentMode = Modes.DEFAULT
            newState = States.DEFAULT
        
        if currentState == States.DEFAULT:
            newState = States.WALL_FOLLOWING
            wallPID.reset()
        elif currentState == States.WALL_FOLLOWING:
            if sonarB.distance(MM) < 2000:
                drivetrain.drive(wallPID.getOutput(), 100, turnPID.getOutput(), True)
            else:
                drivetrain.drive(0, 50, turnPID.getOutput(), True)
            if sonarR.distance(MM) < 200:
                newState = States.TURNING
                turnPID.setNewSetpoint(turnPID.setpoint - 90)
            if abs(gyro.orientation(ROLL)) > 8 or abs(gyro.orientation(PITCH)) > 8: # stepped up to a wall without seeing it
                currentMode = Modes.DEFAULT
        elif currentState == States.TURNING:
            drivetrain.drive(0,0,turnPID.getOutput(), True)
            if turnPID.atSetpoint():
                newState = States.WALL_FOLLOWING

while True:
    # times = []
# loop initialization
    drivetrain.active = False
    arm.active = False
# inputs
    controllerButtons.update()
    camera.update()
    # drivetrain.updateOdometry() # has very little function and does not currently work correctly
    PID.updateAllPIDs()
# scheduling
    Delays.checkAllDelays()
# main run
    stateMachine()
# extra outputs
    arm.updateGripper()
    if not drivetrain.active:
        drivetrain.stopAll()
    if not arm.active:
        arm.stop()
# timing
    prevSystemTime = systemTime
    # while systemTime-prevSystemTime < 100000:
    systemTime = brain.timer.system_high_res()
# logged time usage
    #timeUsageCalc()
    #print("timeUsage:", timeUsage)