---
name: MusicCast Bridge
description: Native Windows receiver controls and PC audio streaming.
colors:
  primary: "#214f7c"
  primary-hover: "#193e62"
  focus: "#286cac"
  slider-active: "#285f94"
  selection: "#d4e5f5"
  workspace: "#eef1f4"
  surface: "#ffffff"
  text: "#182532"
  text-muted: "#526170"
  volume-text: "#193f66"
  status-text: "#245e49"
  notice-text: "#7a311a"
  notice-surface: "#fff0e9"
  field-border: "#8998a6"
  control-surface: "#e1e8ef"
  control-hover: "#d0dfed"
  control-pressed: "#bed2e5"
  disabled-text: "#697786"
  disabled-surface: "#e2e6eb"
  slider-track: "#c5d0db"
  slider-disabled: "#8494a5"
typography:
  display:
    fontFamily: "Segoe UI"
    fontSize: "34pt"
    fontWeight: 600
  headline:
    fontFamily: "Segoe UI"
    fontSize: "22pt"
    fontWeight: 600
  title:
    fontFamily: "Segoe UI"
    fontSize: "13pt"
    fontWeight: 600
  body:
    fontFamily: "Segoe UI"
    fontSize: "10pt"
  label:
    fontFamily: "Segoe UI"
    fontSize: "10pt"
    fontWeight: 600
rounded:
  slider-track: "3px"
  control: "5px"
  notice: "6px"
  slider-handle: "9px"
  panel: "10px"
spacing:
  field: "6px 8px"
  button-block: "6px"
  notice: "12px"
  button-inline: "14px"
  panel-gap: "12px"
  section-gap: "12px"
  column-gap: "20px"
  panel-top: "16px"
  panel-inset: "16px"
  window-block: "16px"
  window-inline: "20px"
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.surface}"
    typography: "{typography.label}"
    rounded: "{rounded.control}"
    padding: "6px 14px"
  button-primary-hover:
    backgroundColor: "{colors.primary-hover}"
  button-secondary:
    backgroundColor: "{colors.control-surface}"
    textColor: "{colors.text}"
    typography: "{typography.label}"
    rounded: "{rounded.control}"
    padding: "6px 14px"
  button-secondary-hover:
    backgroundColor: "{colors.control-hover}"
  button-secondary-pressed:
    backgroundColor: "{colors.control-pressed}"
  button-disabled:
    backgroundColor: "{colors.disabled-surface}"
    textColor: "{colors.disabled-text}"
  field:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text}"
    typography: "{typography.body}"
    rounded: "{rounded.control}"
    padding: "{spacing.field}"
  receiver-panel:
    backgroundColor: "{colors.surface}"
    rounded: "{rounded.panel}"
    padding: "16px"
  notice:
    backgroundColor: "{colors.notice-surface}"
    textColor: "{colors.notice-text}"
    typography: "{typography.body}"
    rounded: "{rounded.notice}"
    padding: "{spacing.notice}"
  volume-readout:
    textColor: "{colors.volume-text}"
    typography: "{typography.display}"
  connection-status:
    textColor: "{colors.status-text}"
    typography: "{typography.label}"
---

# Design System: MusicCast Bridge

## Overview

**Creative North Star: "Windows mixer"**

A light slate workspace contains a white receiver surface, blue controls and a prominent actual-volume readout. Polish and English labels name commands directly. The visual hierarchy follows a desktop utility: connection first, receiver controls together, then PC audio controls.

This is source-derived documentation of `src/musiccast_bridge/ui.py` and the application font in `src/musiccast_bridge/app.py`, informed by `PRODUCT.md` and `docs/desktop-surface.md`. The North Star comes from the existing surface brief. It is an implementation description, not user-approved appearance. No Qt screenshot or Windows runtime was available; rendered verification remains pending.

The sidecar's HTML/CSS specimens illustrate the native tokens; they are not application screens. Its eight-step tonal ramps are generated preview metadata, not additional shipped colors. Qt popup, font, focus and layout behavior still require native checks. A web design detector does not apply to this native Qt surface.

**Key Characteristics:**

- Segoe UI throughout, with the largest type reserved for receiver volume.
- Light neutral surfaces with blue action, selection and keyboard-focus treatments.
- Flat rounded controls, a single receiver panel and explicit textual feedback.
- Native Qt widgets and standard platform media-volume icon; no raster assets.

## Colors

The palette uses blue actions over cool light neutrals, with separate text treatments for connection status and notices. The frontmatter records the exact QSS values.

### Primary

- **Receiver Blue** (`primary`) identifies primary buttons and the slider handle. **Deep Receiver Blue** (`primary-hover`) identifies primary-button hover.
- **Focus Blue** (`focus`) outlines keyboard-focused buttons and fields. **Slider Blue** (`slider-active`) fills the completed slider track.
- **Selection Blue** (`selection`) highlights choices in the combo-box popup.

### Neutral

- **Slate Workspace** (`workspace`) surrounds the **White Surface** (`surface`) receiver panel and fields.
- **Ink** (`text`) carries body copy; **Muted Slate** (`text-muted`) carries subtitles and hints. **Volume Ink** (`volume-text`) distinguishes the large receiver readout.
- **Control Slate** (`control-surface`), **Hover Slate** (`control-hover`) and **Pressed Slate** (`control-pressed`) describe the secondary-button states.
- **Field Stroke** (`field-border`) separates editable fields from surrounding surfaces. **Track Slate** (`slider-track`) shows the remaining slider range.
- **Disabled Text**, **Disabled Surface** and **Disabled Handle** use their corresponding `disabled-*` and `slider-disabled` tokens.
- **Status Green** (`status-text`) styles the connection-status label. The implementation applies it to disconnected, connecting and demo labels too; it is not a success-only semantic token.
- **Notice Rust** (`notice-text`) on **Notice Paper** (`notice-surface`) styles errors, operational notices and the explicit demo warning. This is a shared notice treatment, not a separate error taxonomy.

## Typography

Segoe UI is set both on the application and in the Qt stylesheet. No secondary font, custom tracking or line-height override is declared. Font sizes use points; spacing and component geometry use Qt stylesheet pixels.

- **Display** is the actual receiver-volume readout.
- **Headline** is the application name.
- **Title** marks receiver and PC-audio sections.
- **Body** is the default text, hints, values and fields.
- **Label** is used for buttons and connection status.

Use the frontmatter hierarchy as the source of exact sizes and weights. Do not treat an absent receiver value as a numerical zero: the current readout uses an em dash.

**The Actual State Rule.** The large readout reports receiver state. While dragging, the hint shows the proposed percentage; it does not replace the readout with an unconfirmed value.

## Layout

The native window uses two columns with no scrolling container. Receiver controls occupy the white panel on the left; connection/discovery and PC audio occupy the right. Title, reserved notice and footer span the window. The explicit “Użyj IP” action fills the host field; connection remains a separate action.

Width starts from a target of 1080 logical pixels and the desktop work area. Qt measures the height using actual fonts and layout hints once at startup, then fixes both dimensions and disables maximizing. Discovery and notice slots remain allocated in empty states. Long receiver/status/track/notice strings use bounded one- or two-line slots with ellipsis and full-text tooltips; selectors do not grow with their items. Explicit tab order follows connection, receiver, PC audio and footer.

If the normal layout exceeds the work area, a compact variant uses 9pt body/label text, an 18pt app title, 28pt volume, 4px vertical control padding, 18px minimum control content height, 16×12px outer insets and 12px column/panel insets. It tightens spacing and shortens explanatory hints, retaining their full text in tooltips. The palette is unchanged. A final fit check reports an insufficient work area instead of silently placing controls beyond the screen.

Native rendering, work-area fit and high-DPI behavior still require Windows checks. These are source-derived facts, not a screenshot verification.

## Elevation & Depth

The application defines no drop shadows, gradients or animated elevation. A white receiver panel against the slate workspace supplies tonal separation. The native combo popup, tray menu, window frame and file dialog retain platform behavior and may receive system depth effects.

## Shapes

Controls have gently rounded corners; the receiver panel has the broadest container radius. The notice sits between these two forms. The horizontal volume slider has a slim rounded track and rounded handle. Fields have a single-pixel stroke; focus changes the stroke to a two-pixel blue border. The exact radii are in the frontmatter.

## Components

### Buttons

Primary and secondary `QPushButton` controls share semibold text, recorded padding, rounded corners and a minimum content height of 20 pixels. Primary actions include “Połącz” and “Słuchaj z komputera”; utility and transport actions use the secondary style. Secondary controls define hover and pressed fills. Primary controls define a hover fill but no distinct primary pressed token. Buttons use a transparent single-pixel border at rest and the shared focus border when focused.

Disabled buttons have a dedicated muted fill and text color. A checked-button rule exists, but no current button is made checkable; it is not documented as a shipped toggle component. Text changes such as “Łączenie…” and “Szukanie…” convey pending work.

### Fields and selectors

`QLineEdit` and `QComboBox` share white surfaces, a muted stroke, control radius, field padding and a 20-pixel minimum content height. Focus uses the shared two-pixel blue border. The combo popup uses the selection token. The implementation gives controls accessible names in the selected language; native platform behavior supplies unspecified arrows and selection details.

### Receiver panel

One white rounded `QFrame` groups the receiver name, power action, actual volume, slider, mute, source, track and playback transport. It uses the recorded inset and panel spacing. Descendant-label backgrounds are transparent. Do not infer additional card variants from this single container.

### Volume control

The readout shows the receiver's reported display string when available, otherwise the percentage of its supported range. The slider exposes that percentage range and can be capped by the receiver's current maximum. Its groove is 6 pixels high; the handle is 18 pixels wide with a vertical margin of −7 pixels. A muted handle marks a disabled slider. “Ciszej”, “Głośniej” and “Wycisz” remain text-labelled controls.

### Status and notices

Connection status is a semibold textual label. A reserved two-line notice slot carries demo disclosure, errors or operational guidance, with a transparent empty state. Audio state is a separate bounded two-line hint beside the file test action. Full text remains available in tooltips. Availability is reflected by actual disabled controls according to connection, receiver capabilities and audio state.

### Native desktop surfaces

The receiver panel also contains a compact **Transmisja** table: current RTP
traffic, packet rate, retransmissions, source buffer/silence, resend errors and
maximum sender gap. It uses the existing type and color hierarchy, fixed one-line
values and full-text tooltips. A one-second timer reads passive snapshots; no
capacity test runs. Available bandwidth is explicitly unmeasured. The existing
startup fit pass includes the table, and updates do not resize the fixed window.
Native rendering and work-area fit for this addition still require Windows checks.

The tray menu provides “Otwórz”, “Zatrzymaj dźwięk” and “Zakończ”. The app and tray share Qt's standard media-volume icon. The footer opens a nonmodal Settings window. Its General tab contains the saved language and close-to-tray checkbox; the Windows audio tab contains opt-in default-output switching, target selection, mixer access and route recovery; Licenses and terms displays local read-only documents. Language changes apply after restart. The main window reserves a three-line routing hint, including recovery guidance after a crash. There is no web navigation, chip library or custom icon system in the current build.

## Do's and Don'ts

### Do:

- **Do** preserve the source-derived type hierarchy and shared control geometry.
- **Do** keep the reported receiver value separate from an unconfirmed slider proposal.
- **Do** retain visible text for connection, audio, error and demonstration states.
- **Do** verify the fixed normal/compact layout against the desktop work area and Windows high-DPI scaling.

### Don't:

- **Don't** claim screenshot verification or user approval from this source-only documentation.
- **Don't** interpret the shared green status style as proof of a successful connection.
- **Don't** substitute browser specimens in the sidecar for native Qt rendering tests.
- **Don't** add invented responsive breakpoints, animation tokens, raster assets or unsupported control variants to this recorded system.
