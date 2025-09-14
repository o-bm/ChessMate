#include <AccelStepper.h>
#include <Servo.h>

// Step/dir pins for LONG (Y)
#define STEP_PIN1 11
#define DIR_PIN1 10

// Step/dir pins for SHORT CUSTOM (X)
#define STEP_PIN2 9
#define DIR_PIN2 8

// Microstepping control pins (DRV8825 MS1/MS2/MS3) – shared
#define M0_PIN 7
#define M1_PIN 6
#define M2_PIN 5

// Limit switches (wired to GND, use INPUT_PULLUP)
#define X_LIMIT_PIN 3
#define Y_LIMIT_PIN 4

// servo
Servo myservo;
#define servoPin 13

// Create stepper instances
AccelStepper stepperX(AccelStepper::DRIVER, STEP_PIN2, DIR_PIN2);
AccelStepper stepperY(AccelStepper::DRIVER, STEP_PIN1, DIR_PIN1);

// steps that each axis needs to move 1.125 inches 
const long stepsPerUnitX = 575;
const long stepsPerUnitY = 1155;

void setup() {
  // Setup microstepping pins
  pinMode(M0_PIN, OUTPUT);
  pinMode(M1_PIN, OUTPUT);
  pinMode(M2_PIN, OUTPUT);

  // Example: set to 1/16 microstepping (MS1=HIGH, MS2=HIGH, MS3=LOW)
  digitalWrite(M0_PIN, HIGH);
  digitalWrite(M1_PIN, HIGH);
  digitalWrite(M2_PIN, LOW);

  // Setup limit switches
  pinMode(X_LIMIT_PIN, INPUT_PULLUP);
  pinMode(Y_LIMIT_PIN, INPUT_PULLUP);

  myservo.attach(servoPin);

  // Stepper setup
  stepperX.setMaxSpeed(4000.0);
  stepperX.setAcceleration(2500.0);

  stepperY.setMaxSpeed(4000.0);
  stepperY.setAcceleration(2500.0);

  Serial.begin(115200);
  Serial.println("Ready for commands");
}

void homeAxis(AccelStepper &motor, int limitPin, bool dirTowardSwitch, long offsetStep) {
  motor.setMaxSpeed(3000);
  motor.setAcceleration(2000);

  // First move toward the switch
  motor.moveTo(dirTowardSwitch ? 100000 : -100000);

  while (digitalRead(limitPin) == HIGH && motor.distanceToGo() != 0) {
    motor.run();
  }

  // Immediately stop and reset target (no decel)
  motor.setCurrentPosition(0);
  motor.moveTo(0);

  delay(100);

  // Back off just a few steps
  int backoffSteps = 10;
  motor.moveTo(dirTowardSwitch ? -backoffSteps : backoffSteps); // back off the switch
  motor.runToPosition();

  delay(100);

  // Slow re-approach
  motor.setMaxSpeed(300);
  motor.setAcceleration(2000); // very high accel = almost instant stop
  motor.moveTo(dirTowardSwitch ? backoffSteps * 2 : -backoffSteps * 2); // go forward again a short distance toward the switch until the switch is triggered again

  while (digitalRead(limitPin) == HIGH && motor.distanceToGo() != 0) {
    motor.run();
  }

  // Final stop and zero position
  motor.setCurrentPosition(0);
  motor.moveTo(0);

  Serial.println("Axis homed");

  // reset speeds to fast
  motor.setMaxSpeed(8000);
  motor.setAcceleration(4000);
  // set offset
  motor.setCurrentPosition(offsetStep);
  motor.move(offsetStep);
  while (motor.distanceToGo() != 0) {
    motor.run();
  }
  Serial.println("Axis offset set");
}

void homeAll() {
  Serial.println("Homing X...");
  homeAxis(stepperX, X_LIMIT_PIN, false, 500); // true = home in negative dir
  Serial.println("Homing Y...");
  homeAxis(stepperY, Y_LIMIT_PIN, false, 1500); //3000
  Serial.println("All axes homed and offsets set!");
}

void raiseServo() {
  for (int pos = 180; pos >= 60; pos -= 1) { // Go from 180 to 50 degrees
    myservo.write(pos); // Tell servo to go to position in variable 'pos'
    delay(15); // Wait 15 milliseconds for the servo to reach the position
  }
}

void lowerServo(){
  for (int pos = 60; pos <= 180; pos += 1) { // Go from 50 to 180 degrees
    myservo.write(pos); // Tell servo to go to position in variable 'pos'
    delay(15); // Wait 15 milliseconds for the servo to reach the position
  }
}

void loop() {
  if (Serial.available() > 0) {
    String input = Serial.readStringUntil('\n');  // read full line
    input.trim();

    if (input.length() > 0) {
      if (input == "home") {
        Serial.println("Homing...");
        homeAll();
      }

      if (input == "raise") {
        Serial.println("Raising Servo...");
        raiseServo();
      }

      if (input == "lower") {
        Serial.println("Lowering Servo...");
        lowerServo();
      }
      
      if (input.startsWith("X:")) {
        // Example input: "X:4 Y:-2"
        int xIndex = input.indexOf('X');
        int yIndex = input.indexOf('Y');
        long unitsX = 0;
        long unitsY = 0;

        if (xIndex != -1) {
          int colon = input.indexOf(':', xIndex);
          if (colon != -1) {
            unitsX = input.substring(colon + 1).toInt();
          }
        }
        if (yIndex != -1) {
          int colon = input.indexOf(':', yIndex);
          if (colon != -1) {
            unitsY = input.substring(colon + 1).toInt();
          }
        }

        long stepsX = unitsX * stepsPerUnitX;
        long stepsY = unitsY * stepsPerUnitY;

        Serial.print("Moving X: ");
        Serial.print(unitsX);
        Serial.print(" units, Y: ");
        Serial.print(unitsY);
        Serial.println(" units...");

        stepperX.move(stepsX);
        stepperY.move(stepsY);

        // Run both steppers until they’re done
        while (stepperX.distanceToGo() != 0) {
          stepperX.run();
        }
        while (stepperY.distanceToGo() != 0) {
          stepperY.run();
        }
      }

      Serial.println("Done!");
    }
  }
}