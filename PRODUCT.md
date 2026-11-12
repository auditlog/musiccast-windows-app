# MusicCast Bridge

<!-- impeccable:product-schema 1 -->

## Platform

Windows desktop, Windows 10/11. This is a native Qt application, not a website.

## Stack

Proposed Python + PySide6, existing AirPlay sender pyatv and WASAPI capture.
The user was offered a stack choice; no preference received yet.

## Users

Polish-speaking owner of a Yamaha R-N602, listening from a Windows computer.

## Product Purpose

One application controls the receiver and sends PC audio over the local network.
The accepted scope includes discovery, power/standby, volume/mute, input selection,
current status, and starting PC streaming at the receiver's configured volume.

## Operating Context

The receiver and PC share a home network. Spotify Connect remains available for
Spotify. Other PC audio can use the receiver's existing AirPlay implementation.

## Capabilities and Constraints

- Use capabilities returned by Yamaha Extended Control, including volume bounds.
- Network Standby is required to wake the receiver remotely.
- First version uses ordinary user-mode software, no custom kernel driver.
- AirPlay introduces buffering; measure latency on the user's hardware.
- Loopback mirrors an existing Windows output. Local audio is not automatically muted.
- Receiver-only listening uses a separately installed VB-CABLE endpoint with explicit
  Windows app routing. Source volume and physical speaker mute are then independent.
- Diagnostics measure capture and sender gaps, silence insertion and retransmissions;
  they do not claim per-sample delivery or playback confirmation by the receiver.
- Exact receiver IP, firmware and audio devices have not been supplied.
- The development sandbox cannot invoke Windows or download Python dependencies.

## Product Principles

- Show the actual receiver state, including changes made by other controllers.
- Keep network operations off the GUI thread.
- Keep discovery and reconnection read-only; power/audio changes need a user action.
- Do not invent supported controls or assume a percentage equals a Yamaha volume unit.
- Clearly label demonstration mode and platform limitations.
