# AI Surveillance System — Presentation Speeches
## GLA University | Department of Computer Engg. & Application
## Supervisor: Rohit Sharma

---

## PROJECT OPENING SPEECH
### Person 1 from Role 1 delivers this
**Estimated Time: 2 minutes**
**Demo Required: No**

Good morning respected panel members, our supervisor Rohit Sharma, and my dear friends. We are very happy to present our project on an AI Surveillance System built for real-time safety and smart monitoring. In this project, we have combined hardware sensing, camera streaming, face recognition, cloud storage, Telegram alerts, and a live dashboard into one working system on a Raspberry Pi.

Our complete team is divided into six roles, and each role handles one important part of the system. Role 1 manages the PIR sensor, GPIO pins, LEDs, and buzzer. Role 2 handles the always-on camera and live frame pipeline. Role 3 takes care of face recognition and face enrollment. Role 4 manages Firebase and cloud functions. Role 5 works on Telegram alerts and Google Vision labels. Role 6 presents the dashboard, the user interface, and deployment flow.

In simple words, our system stays ready all the time, but it only starts active scanning when motion is detected. Then it checks whether the person is known or unknown, shows the result on the screen, turns on the correct hardware alert, saves the event to Firebase, and sends a message on Telegram when needed. That means the project does not only detect motion, it also identifies people and records evidence in real time.

This project matters in the real world because security is not just about watching a camera. It is about making a quick decision, reducing manual work, and giving the owner immediate awareness. Our system can help at homes, labs, offices, hostels, and small businesses where continuous monitoring is needed.

Now we will explain the project step by step, starting from the hardware layer and moving all the way to the dashboard and cloud system. With that, I will invite my partner from Role 1 to explain the hardware and GPIO control in detail.

---

## ROLE 1 — Hardware & GPIO Control
### Person A — Name Placeholder
**Estimated Time: 3-4 minutes**
**Demo Required: Yes**

Good morning respected panel members, our supervisor Rohit Sharma, and everyone present here. I am the first speaker from Role 1, and my part is hardware and GPIO control. I will explain how our physical sensing system starts the scan, how the PIR sensor works, and how the LEDs and buzzer react during recognised and unknown events.

First, let me explain the PIR sensor. PIR means passive infrared sensor. It does not send out infrared light itself, but it detects changes in infrared radiation from the surrounding area. Human bodies give off heat, so when a person moves in front of the sensor, the PIR detects a change and sends a signal to the Raspberry Pi. We used it because it is simple, low power, and reliable for motion-based surveillance. Instead of running the full recognition pipeline all the time, the system waits in standby and wakes up only when motion is detected.

In our setup, we use GPIO 23 for the PIR sensor, GPIO 17 for the green LED, GPIO 27 for the red LED, and GPIO 22 for the buzzer. These pins are configured in the software exactly so the system can read motion and show alert status through physical outputs. The code keeps the outputs low at startup so the board begins in a safe state.

The key logic here is the 20 second scan window. When motion is detected, the system marks the time and keeps scanning for 20 seconds. That means the camera and recognition engine stay active only for a short period after motion, which saves CPU power and makes the system feel intelligent. If new motion is detected again during that time, the window is refreshed.

Physically, when the person is recognised, the green LED turns on to show that the system has matched the face with a known user. When the person is unknown, the red LED turns on and the buzzer beeps to warn the user. This gives an immediate local response even before checking the dashboard.

[Wave hand in front of PIR sensor] Now I will wave my hand in front of the PIR sensor. You can see the terminal showing the motion event and the scan window starting. [Point to terminal output] At the same time, the camera shifts from standby to active recognition mode, and the countdown begins from 20 seconds.

[Show LEDs] If the system recognises a known face, you will see the green LED. If it is unknown, the red LED and buzzer will activate together. This is the exact physical response of our hardware layer.

I will now hand over to my partner from Role 1, who will explain the fail-safe logic, the circuit connections, and the viva answers related to GPIO control.

### Person B — Name Placeholder
**Estimated Time: 3-4 minutes**
**Demo Required: Yes**

Good morning respected panel members, our supervisor Rohit Sharma, and everyone present here. I am continuing from my partner, and I will explain the fail-safe behavior, circuit reasoning, and the important viva points for the hardware section.

Our hardware design is meant to be safe even when something is missing or not connected. In the code, if the GPIO library is not available, the system does not crash. Instead, it falls back to a soft mode and keeps the software running. That is important because it allows us to test the project on a non-Pi machine or in a development setup without physical GPIO access. The software still keeps its main logic alive, and only the hardware outputs are skipped.

The LED and buzzer connections are simple but meaningful. The green LED is connected to the recognition signal because green naturally means safe, verified, or allowed. The red LED is connected to unknown detection because red means caution or warning. The buzzer is paired with the red alert so the system can attract attention instantly when an unrecognised person is found. This combination gives both visual and audible feedback.

Now let me answer the viva questions clearly.

Q: Why did you use GPIO 23 for PIR?
A: We used GPIO 23 because it was free, easy to map in BCM numbering, and suitable as a stable input pin for the PIR sensor. The project keeps a clear separation between the motion input and the alert outputs.

Q: What is the purpose of 20 second timer?
A: The 20 second timer gives the camera enough time to scan the scene after motion is detected. It avoids continuous high CPU usage and ensures the system only performs active recognition for a limited window.

Q: What happens if GPIO library is not available?
A: The software switches into fail-safe mode and continues running without physical outputs. This prevents the whole surveillance system from stopping just because the hardware library is missing.

Q: Why buzzer beeps 3 times for unknown?
A: Three beeps are noticeable, easy to recognise, and not too long. They make the unknown-person alert distinct from normal system noise.

Q: How does the Pi know to stop scanning after 20 seconds?
A: The program stores an end time for the scan window and keeps comparing the current monotonic time with that value. Once the time is over, the system returns to standby mode automatically.

[Point to GPIO wiring diagram] So in short, the hardware layer is not only about switching components on and off. It is about making the system safe, understandable, and useful in real-time security. I will now hand over to Role 2, where my partner will explain the camera streaming and frame pipeline.

---

## ROLE 2 — Camera Streaming & Frame Pipeline
### Person A — Name Placeholder
**Estimated Time: 3-4 minutes**
**Demo Required: Yes**

Good morning respected panel members, our supervisor Rohit Sharma, and everyone present here. I am the first speaker from Role 2, and I will explain how the camera stays always on, how we stream frames to the browser, and why we selected this camera approach for the project.

We use the Picamera2 library because it is designed for the Raspberry Pi camera stack and works closely with libcamera. That makes it a better choice for the Pi than `cv2.VideoCapture`, which is often less reliable on Pi camera hardware and can add extra latency. Our aim was to keep the camera stable for long periods, because the surveillance system is supposed to be always available.

The camera module we used is the OV5647-based Pi camera module, which is commonly used on Raspberry Pi projects because it is compact and suitable for real-time monitoring. The concept behind our design is that the camera never really turns off. It keeps capturing frames in the background, while the recognition logic decides whether to process those frames deeply or only show them on the dashboard.

We chose 640 by 480 resolution because it gives a good balance between clarity and speed. A larger resolution would take more processing time and increase lag, while a smaller resolution could reduce accuracy. For surveillance, we need enough detail to recognise faces, but we also need the system to stay responsive on a Raspberry Pi.

At the start, we experimented with MJPEG-style live updates, but that approach can become laggy when the network or browser refresh rate is not ideal. In our current design, the dashboard uses base64 polling from the `/api/frame` endpoint, which returns the latest JPEG frame as encoded text. That approach reduced the lag and made the browser refresh feel smoother and simpler to manage.

[Open browser dashboard] Now I will open the browser and point to the live feed. [Point to live feed] You can see that the feed stays active, and the dashboard keeps refreshing the image without requiring a page reload. What is happening behind the scenes is that the Pi camera continuously captures frames, the backend stores the most recent one, and the browser fetches the latest frame at a fast interval.

So the main idea is very simple: the camera is always on, the dashboard is always ready, and the system only decides whether to do heavy recognition or just present a live preview. I will now hand over to my partner from Role 2, who will explain threading, frame locking, the `/api/frame` endpoint, and the viva answers.

### Person B — Name Placeholder
**Estimated Time: 3-4 minutes**
**Demo Required: Yes**

Good morning respected panel members, our supervisor Rohit Sharma, and everyone present here. I am continuing from my partner, and I will explain how the recognition thread is separated from the stream thread, why frame locking is needed, and how the browser receives live frames from the Pi.

In our system, the camera capture is separated from the recognition logic so that one part can keep collecting frames while another part analyzes them. This is very important because if both tasks tried to control the camera at the same time, the feed could become unstable or even stop. The code uses a dedicated capture thread and then shares the latest frame safely with the rest of the program.

That safe sharing is done with `frame_lock`. In simple words, a lock is like a turn-taking rule. When one thread is reading or writing the latest frame, the other thread waits for a moment. This avoids half-written frames, corrupted images, or strange display glitches in the browser. It is a small detail, but it makes the whole stream more dependable.

The browser receives live frames from the `/api/frame` Flask endpoint. That endpoint reads the newest frame, compresses it into a small JPEG, and returns it in base64 format. On the dashboard side, the JavaScript code requests a new frame about every 100 milliseconds, which is roughly 10 frames per second. That is enough for a smooth user experience without overloading the Pi.

Now I will answer the viva questions clearly.

Q: Why does the camera always stay on?
A: The camera stays on so the system can respond immediately when motion happens. It avoids startup delay and makes the surveillance feel continuous.

Q: Why was MJPEG laggy and how did you fix it?
A: MJPEG can become laggy when the stream handling is heavy or the browser refresh rate is not ideal. We fixed it by using fast base64 frame polling from the `/api/frame` route, which simplified delivery and reduced visible delay.

Q: What is frame_lock and why is it needed?
A: Frame lock is a threading safety mechanism. It prevents one thread from reading a frame while another thread is in the middle of writing it.

Q: What resolution does the camera stream at?
A: The system streams at 640 by 480 resolution. That resolution is chosen to balance speed, clarity, and recognition accuracy.

Q: How does the browser receive live frames?
A: The browser calls the Flask frame endpoint repeatedly, gets the newest JPEG as base64, and displays it inside the image tag on the dashboard.

[Point to live frame refresh] So the camera layer is built for stability, speed, and low lag. I will now hand over to Role 3, where my partner will explain the face recognition engine and the enrollment process.

---

## ROLE 3 — Face Recognition & Enrollment
### Person A — Name Placeholder
**Estimated Time: 3-4 minutes**
**Demo Required: Yes**

Good morning respected panel members, our supervisor Rohit Sharma, and everyone present here. I am the first speaker from Role 3, and I will explain how face recognition works, how enrollment happens, and why our known faces folder is structured the way it is.

We use the `face_recognition` library by Adam Geitgey because it provides a direct and practical way to detect faces, generate encodings, and compare them against known people. Under the hood, it depends on dlib, which is a powerful computer vision library. On the Raspberry Pi, dlib compilation took around 20 minutes because it is a heavy native dependency and needs to build carefully for the Pi hardware. That was a real part of our development process, and it shows that the face engine is not a toy example.

Our known faces are stored in the `known_faces` folder, and each person has their own folder name. That structure makes it easy to manage multiple users. For example, if a person named Ansh is enrolled, their images stay inside a folder named after them. The system scans that folder at startup and loads all face encodings into memory.

The enrollment flow is simple. First, the dashboard asks for a name. Then it captures the current live frame from the camera. After that, the system checks whether a face is present in the frame. If a face is detected, the image is saved under the matching folder, and the face database is reloaded so the new person becomes active immediately. This means the user does not need to restart the whole system after enrollment.

The important concept here is face encoding. A face encoding is a numeric representation of a person’s face. Instead of storing the raw image only, the system converts the face into a vector of features. That vector helps the software compare one face against another very quickly.

[Capture a face during demo] Now I will demonstrate enrollment. [Enter name in dashboard] I will enter a name, click enroll, and capture the face from the live feed. [Show success message] As soon as the image is saved, the system reloads the encodings and prepares that identity for future recognition.

[Trigger next scan] When the next motion scan happens, the system checks the same face again. If it matches the new enrollment, the dashboard shows the person as recognised. This is the exact end-to-end face recognition and enrollment flow of our project.

I will now hand over to my partner from Role 3, who will explain tolerance, upsample, the model choice, and the viva answers in more technical detail.

### Person B — Name Placeholder
**Estimated Time: 3-4 minutes**
**Demo Required: Yes**

Good morning respected panel members, our supervisor Rohit Sharma, and everyone present here. I am continuing from my partner, and I will explain the technical settings that affect recognition quality and reliability.

The first important setting is `tolerance=0.45`. This number controls how strict the matching is. A lower tolerance means the system only accepts closer matches, so it reduces false recognition. We selected 0.45 because it was a practical balance for our project. It is stricter than the common default of 0.6, which makes the system more careful in surveillance conditions where we want fewer mistakes.

The second important setting is `upsample=2`. Upsampling means the detector looks more carefully at the image by scaling it internally to find faces that may be smaller or farther away. We used it because a CCTV-style camera does not always capture a face very close to the lens. Upsampling helps the system detect faces even when the subject is not standing directly in front of the camera.

We chose the HOG model instead of the CNN model because HOG is lighter and more suitable for Raspberry Pi performance. CNN can be more accurate, but it needs much more computing power. Since our project must run in real time on edge hardware, HOG gives us a practical balance.

When a face is recognised, the system draws a green rectangle. When it is unknown, it draws a red rectangle. This visual coding is simple and instantly understandable. Green means safe or matched, while red means unknown and possibly suspicious.

The system also reloads encodings after new enrollment without restart. That is done by reloading the known faces list in the background, so the new user becomes part of the recognition engine immediately.

Now I will answer the viva questions clearly.

Q: What is face encoding?
A: Face encoding is the numeric feature vector created from a face image. It allows the system to compare one face with another mathematically instead of comparing images by eye.

Q: Why tolerance 0.45 and not 0.6?
A: We used 0.45 because we wanted stricter matching and fewer false recognitions. The value 0.6 is more permissive, but in surveillance we prefer caution.

Q: What is upsample and why use it?
A: Upsample makes the detector scan the image more carefully for smaller faces. We use it to improve recognition from CCTV distance and in less-than-perfect camera angles.

Q: What happens if enrolled image has no face?
A: The system rejects that image and does not save it as a valid enrollment sample. This protects the database from bad data.

Q: How does system recognise from CCTV distance?
A: It uses face detection with upsampling, face encoding comparison, and a tolerance threshold that is tuned for surveillance use. That combination helps it work even when the face is not very close.

[Point to recognised face box] So this role turns raw camera frames into identity decisions. I will now hand over to Role 4, where my partner will explain Firebase, the database structure, and cloud functions.

---

## ROLE 4 — Firebase & Cloud Functions
### Person A — Name Placeholder
**Estimated Time: 3-4 minutes**
**Demo Required: Yes**

Good morning respected panel members, our supervisor Rohit Sharma, and everyone present here. I am the first speaker from Role 4, and I will explain how our Firebase integration stores recognition events and how the cloud side extends the local system.

Our Firebase project is set up under the name `ai-surveillance-vision`. That project acts as the cloud home for our surveillance records. The main database we use for recognition history is Firebase Realtime Database. In our code, each event is stored under a path that includes the device ID and a timestamp or frame identifier. This gives us a clean, structured timeline of events.

For each recognition event, we store the important fields needed for monitoring and auditing. These include the name of the person, the status, the confidence value, the Vision API labels, the timestamp, and the device ID. In the actual event payload, we also keep Telegram status and the local frame path, so the event can be traced later if needed.

We also use Firebase Storage for captured frames. That is useful because the image can be uploaded once and then processed by a cloud function. It helps us keep a record of the actual frame that triggered the event, instead of storing only text.

[Open Firebase console] Now I will show the live cloud data. [Point to database] After a face scan, you can see the new recognition entry appear in the Realtime Database. [Point to stored frame area] The image is also available in Storage when the cloud upload flow is used.

This is important because the dashboard gives a local view, but Firebase gives a remote view. If the owner is away from the Raspberry Pi, they can still check what happened, when it happened, and how the system classified the event.

I will now hand over to my partner from Role 4, who will explain the cloud function in `index.js`, the upload trigger, service accounts, IAM roles, and the viva answers.

### Person B — Name Placeholder
**Estimated Time: 3-4 minutes**
**Demo Required: Yes**

Good morning respected panel members, our supervisor Rohit Sharma, and everyone present here. I am continuing from my partner, and I will explain the cloud function pipeline and the security setup behind it.

The cloud function is written in `index.js`, and it uses `onObjectFinalized` from Firebase Functions. That means it automatically runs when a new object is completely uploaded to Firebase Storage. In our project, the function is designed to process files under the `frames/` folder. If the uploaded file is not an image or does not match the expected path pattern, the function safely skips it.

After a frame upload is accepted, the function sends the image to Google Cloud Vision, collects labels, faces, and object information, and then writes the result back into the Realtime Database. This gives us cloud-enriched metadata, not just a raw image upload.

The service account JSON is needed because the backend has to authenticate securely to Google Cloud services. It tells the system which project it belongs to and what permissions it has. Without that file, the function would not be able to access Storage, Realtime Database, or Vision API in a trusted way.

The IAM roles are also important. Storage Object Admin allows the function to work with uploaded files. Firebase Realtime Database Admin allows it to write recognition results into the database. Service Account Token Creator helps with secure authentication flows. These roles are part of making the cloud side work correctly and safely.

Now I will answer the viva questions clearly.

Q: What is Firebase Realtime Database?
A: Firebase Realtime Database is a cloud-hosted NoSQL database that stores data in a JSON tree. It is useful for fast event updates and live monitoring.

Q: How does Cloud Function trigger automatically?
A: It triggers automatically when a file is finalized in Firebase Storage. That means the upload is complete and ready for processing.

Q: What is a service account and why do we need it?
A: A service account is a secure identity for backend applications. We need it so the cloud function can authenticate and access Google Cloud services without using a personal user account.

Q: What data structure is stored in Firebase?
A: The project stores a structured recognition event with fields like device ID, name, status, confidence, labels, timestamp, and related metadata. It is stored under a hierarchical path for easy retrieval.

Q: Why use Firebase instead of a local database?
A: Firebase gives us remote access, live updates, and easier cloud integration. A local database would be harder to access from outside the Raspberry Pi and would not support real-time cloud workflows as simply.

[Point to database updates] So this role makes the project cloud-aware and traceable. I will now hand over to Role 5, where my partner will explain the Vision API and Telegram bot alerts.

---

## ROLE 5 — Telegram Bot & Vision API
### Person A — Name Placeholder
**Estimated Time: 3-4 minutes**
**Demo Required: Yes**

Good morning respected panel members, our supervisor Rohit Sharma, and everyone present here. I am the first speaker from Role 5, and I will explain the Google Vision API part of the project and how it is different from face recognition.

We use Google Cloud Vision API to understand what is inside an image. When a frame is sent to Vision, it can return labels such as person, face, electronics, indoor, or other objects depending on the scene. These labels do not tell us who the person is. They only tell us what kind of content appears in the frame.

That is the key difference between Vision API and face_recognition. Vision API answers the question, "What is in this image?" Face recognition answers the question, "Who is this person?" Both are useful, but they solve different problems. In our system, face recognition handles identity, while Vision API adds context.

The Vision API needs credentials and cloud billing support because it is a managed Google Cloud service. That means the project must be connected to the correct Google Cloud account, and the API must be enabled in the same project. This gives us reliable cloud-based labeling for active frames.

[Trigger scan] Now I will trigger a scan and show how the Vision labels appear in the cloud and dashboard. [Point to Firebase/Dashboard] When the frame is processed, labels like person or electronics can appear, giving extra scene context alongside the face result.

This is useful because sometimes the face result alone is not enough. If an unknown person enters the scene, Vision labels can still help us understand the environment and the type of activity in the image.

I will now hand over to my partner from Role 5, who will explain how we created the Telegram bot, how alerts are sent, and the viva answers.

### Person B — Name Placeholder
**Estimated Time: 3-4 minutes**
**Demo Required: Yes**

Good morning respected panel members, our supervisor Rohit Sharma, and everyone present here. I am continuing from my partner, and I will explain the Telegram alert pipeline in a simple but complete way.

We created the Telegram bot using BotFather, which is the official Telegram tool for registering new bots. After creating the bot, we received a token, and that token is used in the Python `python-telegram-bot` library. The chat ID is obtained by opening a conversation with the bot and reading the target chat identifier, which tells the bot where to send messages.

Our system sends two kinds of alerts. If a person is recognised, the alert shows a green check style message with the name, confidence, and photo. If the person is unknown, the alert shows a red warning style message with the alert text and photo. This gives the user immediate mobile notification with visual proof.

The reason we use Telegram instead of email or SMS is speed and simplicity. Telegram messages arrive quickly, support images easily, and work well on any smartphone with internet access. It also avoids the delays and extra cost that SMS can bring.

Now I will answer the viva questions clearly.

Q: What is the difference between Vision API and face_recognition?
A: Vision API tells us what objects or scenes are in the image. Face recognition tells us which known person is in the image.

Q: How did you create the Telegram bot?
A: We created it through BotFather, obtained the bot token, and connected it to the Python Telegram library in our project.

Q: What information does the alert message contain?
A: The alert message contains the status, the person name if known, the confidence value, the timestamp, the device ID, and the captured photo.

Q: Why use Telegram instead of email or SMS?
A: Telegram is faster, simpler, and supports rich photo alerts easily. It is also easy to use on mobile devices without extra gateway setup.

Q: How does Vision API billing work on free tier?
A: The free tier gives limited usage, and after that the project may require billing. That is why the API must be enabled carefully and used within the allowed quota.

[Show Telegram alert on phone] So this role connects the surveillance system to the user’s phone in a fast and practical way. I will now hand over to Role 6, where my partner will explain the dashboard and deployment.

---

## ROLE 6 — Dashboard UX & Deployment
### Person A — Name Placeholder
**Estimated Time: 3-4 minutes**
**Demo Required: Yes**

Good morning respected panel members, our supervisor Rohit Sharma, and everyone present here. I am the first speaker from Role 6, and I will explain the dashboard layout, the route structure, and how the web interface keeps the whole system visible to the user.

Our dashboard has five main parts. First, there is the status bar, which shows camera state, Firebase connection, Vision API state, PIR status, and countdown information. Second, there is the live feed area, which shows the camera stream. Third, there is the verification panel, which shows the latest person name, confidence, labels, timestamp, and Telegram status. Fourth, there is the enroll panel, where new users can be added. Fifth, there is the alerts log, which shows the recent recognition events.

These panels are served through Flask routes in the web layer. The dashboard page itself is loaded from the application, while the API routes provide live JSON updates. The system uses polling so the page stays fresh without needing manual reloads. In our current design, `/api/status` is refreshed every 1 second, and `/api/recognitions` is refreshed every 3 seconds. That gives the user quick status updates while keeping the cloud requests manageable.

Another useful feature is the camera source switcher. The dashboard can show the Pi camera feed or switch to the device camera in the browser. This makes the system more flexible during demos and testing. For example, if the Pi camera is being used for the main surveillance flow, a browser camera can still be used to test recognition in a live session.

[Open dashboard on browser] Now I will walk you through each panel. [Point to status bar] This shows the current system health. [Point to live feed] This is the camera view. [Point to verification panel] This shows the latest recognition result. [Point to enroll panel] This is where we capture a new face. [Point to alerts table] This is the log of recent events.

So the dashboard is not only for viewing. It is also for control, enrollment, and monitoring. I will now hand over to my partner from Role 6, who will explain start.sh, ngrok, deployment, SD card usage, and the viva answers.

### Person B — Name Placeholder
**Estimated Time: 3-4 minutes**
**Demo Required: Yes**

Good morning respected panel members, our supervisor Rohit Sharma, and everyone present here. I am continuing from my partner, and I will explain how we deploy the system, how it becomes publicly accessible, and why the setup is practical for a Raspberry Pi device.

The single-command deployment flow is handled by `start.sh`. That script starts the dashboard application, then starts the monitoring daemon, and if ngrok is installed it also creates a public tunnel. This is very convenient during demonstrations because the team can start the whole system with one command instead of opening multiple terminals manually.

Ngrok is used to expose the local dashboard on a public URL. That means the dashboard can be opened from outside the local network when the tunnel is running. If ngrok is available, the script prints the public dashboard link so it can be shared easily during the presentation.

The system can run on any WiFi network because the Pi only needs network access to reach Firebase, Telegram, and the dashboard tunnel when needed. The camera, face recognition, and GPIO control still work locally on the Raspberry Pi, so the core function is not dependent on a special network setup.

We also mention that a 16GB SD card is sufficient because the project is lightweight in storage terms. The system mainly stores code, a small set of known face images, logs, and temporary frames. It is not a full video archive system, so it does not need large storage to work reliably.

Now I will answer the viva questions clearly.

Q: How do you access dashboard from outside the network?
A: We use ngrok to create a public tunnel to the local Flask server. That gives us a public dashboard URL that can be opened from another network.

Q: What happens if Flask crashes?
A: The local monitoring daemon can still keep running, and the system logs help us identify the issue. In a deployment setup, the process can be restarted through the startup script or a service manager.

Q: Why is 16GB SD card enough?
A: The project stores code, configuration, small face samples, and temporary files. It does not need large video storage, so 16GB is enough for normal operation.

Q: How does the system start automatically?
A: The startup script launches the dashboard and monitoring process together. In a full deployment, this can also be wired into boot-time service management.

Q: What is the URL to access the dashboard?
A: The dashboard is available at the local HTTPS Flask address on port 5000, and if ngrok is active, it also gets a public dashboard link from the tunnel.

[Point to start script] So the deployment is simple, practical, and demo friendly. With that, I will hand over to the closing speaker for Role 6.

---

## PROJECT CLOSING SPEECH
### Person 2 from Role 6 delivers this
**Estimated Time: 1.5 minutes**
**Demo Required: No**

Good morning respected panel members, our supervisor Rohit Sharma, and everyone present here. Thank you for giving us your time and attention. On behalf of the entire team, I would like to conclude our presentation by saying that this project is the result of careful teamwork across hardware, computer vision, cloud integration, alerting, and dashboard design.

We built an AI surveillance system that can stay always on, detect motion with a PIR sensor, recognize familiar faces, alert against unknown persons, save events to Firebase, send Telegram notifications, and show everything on a real-time dashboard. We also achieved strong practical results, including around 79.3 percent face recognition confidence in our tested setup, Telegram alerts in under 2 seconds, zero-lag always-on camera monitoring, and a complete admin dashboard for control and review.

The main value of our project is that it combines local intelligence with cloud visibility. It does not just detect motion. It explains what happened, who was detected, and what action was taken. That makes it useful for real environments where security needs both speed and clarity.

In the future, we would like to improve the system with stronger analytics, better mobile support, more flexible configuration, and possibly expanded storage for longer event history. These are natural next steps, but the current version already demonstrates a complete working surveillance pipeline.

Once again, thank you to our supervisor Rohit Sharma and to the panel for your kind attention. We now invite your questions and feedback.
