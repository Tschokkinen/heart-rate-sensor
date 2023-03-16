# heart-rate-sensor
Code for RaspberryPi Pico W heart rate sensor

The program was written as part of the Data Collection and Processing course.
The program could be more structured (e.g. split functionality to different files), but that was due to the time limitations experienced during the course.

HRV is calculate using MSSD (Mean of the Squared Successive Differences), but using RMSSD would probably be a better/the right solution. 

The program won't be updated further because the RaspberryPi Pico W hardware isn't accessible anymore. Due to this the MSSD and RMSSD differences cannot be tested either.

<b>
NOTE: The MQTT parts were written together with the course instructor, but the rest of the code is entirely self-written created solution.
</b>
