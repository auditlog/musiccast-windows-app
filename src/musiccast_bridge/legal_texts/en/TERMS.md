Terms of use

MusicCast Bridge's own code is provided under the MIT license in LICENSE.
Use, modification, and redistribution, including commercial use, are permitted
subject to its copyright and license notice requirements. These explanations
do not restrict rights granted by MIT or third-party licenses.

The program can check GitHub for stable releases at startup; this can be disabled
in settings. After an update notification, the user opens the release page,
downloads the installer, and runs it after quitting the application.

The program controls the selected receiver on the local network. Starting a
stream may wake it and select AirPlay. You choose the Windows playback output
to capture. Other applications and notifications using that output may also
be sent to the receiver. AirPlay introduces latency; synchronization with
video on the computer is not provided.

Automatic Windows default-output switching is optional and disabled by default.
It changes console and multimedia playback defaults, leaving the microphone
and communications default unchanged. Applications with their own output
assignment in the Windows mixer may need to be set to Default or CABLE Input.
Stopping, stream failure, or quitting attempts to restore the previous output.
A subsequent manual output change is respected. After a process crash or a
device disconnection, use Restore output in settings or select the output in
Windows. Closing to the tray keeps the application and stream running.

The MIT warranty disclaimer and liability limitation apply to the extent
permitted by law; mandatory statutory user rights are unaffected. See
THIRD_PARTY_NOTICES.md for dependencies. VB-CABLE is a separate VB-Audio Software
donationware product and is not relicensed under MIT by this installer.
