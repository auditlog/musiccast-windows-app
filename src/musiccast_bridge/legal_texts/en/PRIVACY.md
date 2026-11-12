Privacy

The application has no user accounts, analytics, or automatic report uploads.
Discovery, receiver control, and audio streaming use the local network. Audio
is captured in memory and sent to the selected receiver; recordings are not
saved to disk.

Update checks, enabled at startup by default, use HTTPS to api.github.com
to read the selected repository's latest stable release. GitHub receives your
IP address and the application version in the User-Agent header. Requests do
not include audio, your Yamaha's address, AirPlay credentials, or diagnostics.
Disable startup checks in Settings → Updates. Manual checks make the same request.

Clicking “Download update” downloads the installer over HTTPS from GitHub and its
file servers (release-assets.githubusercontent.com or objects.githubusercontent.com).
GitHub receives your IP address and app version. The file is saved in the updates
subdirectory of the app's local data. Before launching it, the app checks its size
and SHA-256 against the release metadata. Installation requires a separate click,
closes the app and runs its installer. Downloads and installations never start
automatically in the background.

Settings, logs, and the previous audio-route journal are stored locally in
%LOCALAPPDATA%\MusicCastBridge. They include language, receiver address,
audio device name/identifier, and preferences. AirPlay passwords and pairing
data are stored in Windows Credential Manager, not in settings or diagnostics.
Logs may contain IP addresses, device names, connection times, and error
counters. Review reports before sharing them manually.
Settings also include the update repository, startup-check preference, and
a marker for the last language selection in the installer. The
repository address is embedded in built applications; GitHub passwords and
tokens from Git configuration are not included.

External links open your browser and are subject to the destination site's
policies. Building an installer may download dependencies and VB-CABLE; the
finished installer includes these files. The separate VB-CABLE installer is
subject to its vendor's terms.

Uninstalling preserves settings, logs, credentials, and the shared VB-CABLE
driver. To remove application data, quit, restore your Windows playback output,
delete %LOCALAPPDATA%\MusicCastBridge, and remove the MusicCast Bridge entries
from Windows Credential Manager. Keep the shared driver if other software
uses it.
