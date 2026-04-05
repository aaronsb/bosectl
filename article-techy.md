# I Got Mad About a Firmware Update and Reverse-Engineered My Headphones in Two Hours

I bought the Bose QC Ultra 2 to replace my seven-year-old QC 35s. The ear muffs were falling apart, the micro USB cable was worn through, and I figured — time to upgrade. Turned them on, heard the familiar "Battery 60 percent," felt that satisfying first seal of fresh ear cups. Good start.

Then I opened the app.

Firmware update pending. I'd seen the posts. Firmware 8.2.20, pushed February 10, 2026. Hundreds of threads on Reddit. A TechRadar headline reading "'I am extremely angry!'" A community poll where 65% of owners reported losing features. A structured feedback campaign organized by frustrated users. Bose's official response: "designed to streamline and modernize the user experience... no plans to restore the previous functionality."

I updated anyway because I wanted to see for myself.

Sure enough. Beep boop. No more "Connected to Pixel 8 Pro." Just tones. The battery level check via the volume strip — gone. Single-button device switching for multipoint — gone. And now my $430 headphones require a phone app to adjust the noise cancellation slider. You don't technically need a Bose account for that — but you do need the app, which means you need a supported phone, in a supported region, with a working Bluetooth connection to a device that isn't your Linux workstation. No rollback possible.

So I did what any reasonable person would do. I opened a terminal, connected Claude Code, and started sending bytes.

## Two Hours With an AI Coding Agent

Here's what makes this story different from the typical reverse-engineering writeup. This wasn't weeks of careful analysis. It was two focused sessions — about two hours of actual work — with Claude as my coding agent, iterating in real time while wearing the headphones.

The workflow looked like this: I'd form a hypothesis about how the protocol worked, describe it conversationally, and Claude would write the code to test it, run it against the live headphones, parse the response, and help me figure out what we were looking at. When a test failed, we'd adjust the approach in seconds rather than minutes. When something worked, we'd immediately build on it.

The first session was pure exploration. I knew the headphones spoke Bluetooth, so I had Claude open an RFCOMM socket and start probing. We found the BMAP protocol on channel 2 by trying all 30 channels. We enumerated every function block by sending GET requests and cataloguing the responses. We captured traffic while I toggled settings in the app, diffing the before-and-after state to figure out which bytes changed. By the end of that session we could switch ANC modes and read battery level — without the app.

The second session was where it got interesting. We'd already noticed that Bose's cloud authentication blocked SET commands, but we wondered about SETGET — the "write and read back" operator. Claude wrote a systematic test harness that tried SETGET on every function across every block, ran it, and parsed the results in one shot. Most of the Settings block came back with STATUS responses instead of auth errors. We had EQ control within minutes of that discovery. Then we found the ModeConfig SETGET on the AudioModes block, which gave us the noise cancellation slider — the one thing everyone was most angry about losing control over.

By the end of those two hours we had a working CLI tool with twenty commands, profile management, colored output, auto-detection of paired headphones, and comprehensive protocol documentation. We went from "I wonder what happens if I send bytes to this thing" to a published GitHub repo with a README, MIT license, and a post on r/bose.

I want to be precise about what the AI agent did and didn't do here. The key insights — DNS-hijacking the Bose cloud API to see what still worked, noticing that the app used START instead of SET for mode switching, deciding to test SETGET systematically — those were human pattern-recognition moments. The agent's contribution was eliminating the friction between having an idea and testing it. Instead of writing a Python script, running it, reading the output, editing the script, running it again — I described what I wanted to try and watched it happen in real time. The iteration cycle collapsed from minutes to seconds.

This is what coding agents are actually good at. Not replacing the thinking, but removing the mechanical overhead so you can stay in the flow of investigation. I could keep my headphones on, keep the music playing, and feel the ANC change as we sent commands. The feedback loop was immediate and physical.

## What We Found

Bose headphones speak a protocol called BMAP — Bose Messaging and Protocol — over a Bluetooth serial connection. Every setting you can see in the app — noise cancellation level, EQ, spatial audio, device name, button mapping — is just a BMAP packet. Four-byte header, function block, function ID, operator, payload.

Bose locks write operations behind cloud-mediated ECDH P-384 authentication. When the app changes a setting, the headphones issue a cryptographic challenge, the app forwards it to Bose's servers, Bose signs it, and the response goes back. Genuinely sophisticated — I was impressed.

But Bose didn't gate every operator. Three gaps:

1. **START on AudioModes is unauthenticated.** This is the operator the app uses for real-time mode switching. It lets you switch between Quiet, Aware, Immersion, and custom modes instantly.

2. **SETGET on AudioModes is unauthenticated.** While SET requires auth, SETGET does not. Custom mode slots accept full configuration: noise cancellation level, spatial audio, wind block, and ANC settings.

3. **SETGET on Settings is unauthenticated.** The entire Settings block — EQ, device name, sidetone, multipoint, auto play/pause, button mapping — accepts SETGET without auth.

This isn't an exploit. No keys are extracted. No encryption is broken. No traffic is replayed. The headphones explicitly accept these commands through a standard protocol operator. We're talking to our own hardware through an interface the firmware supports.

## The Tool

The result is `bosectl` — a command-line tool that gives you full control over your QC Ultra 2 from Linux:

```
bosectl status              # Battery, mode, CNC, EQ, all settings
bosectl cnc 7               # Set noise cancellation to 7/10
bosectl eq 5 0 -3           # Bass +5, mid flat, treble -3
bosectl spatial head        # Spatial audio with head tracking
bosectl profile set Focus cnc=8 spatial=off
bosectl Focus               # Switch to it by name
bosectl name "Hotrod"       # Rename your headphones to anything
```

No app. No account. No cloud. No phone.

Every function in the code is documented with the exact BMAP packet format, so anyone can read it and build their own implementation in whatever language they prefer. The protocol documentation covers every function block, payload format, and error code we encountered.

## The Broader Point

There are two stories here.

The first is about device ownership. This is a $430 pair of headphones with a Qualcomm processor running locally on your head. There is no technical reason any setting needs to transit Bose's cloud. The headphones have all the logic to process these commands directly — we proved that by sending them. The cloud exists to keep you in the app. The app exists to keep you in the ecosystem. None of that makes your music sound better.

The second story is about what's possible now with AI coding agents. Two years ago, this reverse-engineering project would have taken a week of evenings — writing scripts, looking up Bluetooth APIs, parsing hex dumps by hand, iterating slowly. With an agent handling the mechanical work, the bottleneck shifted from "can I write the code fast enough" to "can I think of what to try next." And honestly, the ideas came faster because I wasn't losing flow to boilerplate.

This is the part that I think matters for people building things. The agent didn't have some magic insight about Bluetooth protocols. It was fast, it was tireless, it wrote clean code, and it never lost context across a two-hour debugging session. That let me stay in the investigative mindset — forming hypotheses, testing them, building on results — instead of constantly switching between thinking and typing. The quality of the work came from the human-agent loop, not from either side alone.

## De-enshittification as a Service

Let me be clear about what this is and isn't. A firmware update could close these gaps tomorrow. This isn't a permanent jailbreak — it's a tool that works against the current firmware because Bose left a door open in their protocol.

But here's what's changed: the time it takes to respond to enshittification has collapsed. When a company removes features from a product you own, the traditional response was to complain on Reddit, hope for a rollback, or switch brands. Now there's another option — someone with domain curiosity and an AI coding agent can build a working alternative in an afternoon and ship it to everyone affected by evening.

I think this is going to happen a lot more. Not because AI makes reverse engineering trivial — the insights still require human intuition and domain knowledge. But because the gap between "I understand how this works" and "here's a working tool with enough documentation for anyone to build on" has shrunk from weeks to hours. The economics of fighting back against anti-consumer decisions just changed.

`bosectl` doesn't completely de-enshittify the QC Ultra 2. It can't restore the on-device voice prompts or undo the firmware changes. But it gives you a direct channel to your own hardware that doesn't route through anyone's cloud, anyone's app store, or anyone's business model. It's a Python script — not a polished application. But every function is documented with the exact bytes it sends and why, and the protocol notes cover every function block, payload format, and error code we found. The point isn't the tool itself — it's that the documentation makes it straightforward for someone to build a proper system tray widget, a PipeWire integration, or a cross-platform GUI without having to reverse-engineer anything from scratch.

## Try It

Everything is open source under MIT: [github.com/aaronsb/bosectl](https://github.com/aaronsb/bosectl)

If you're running Linux and you own Bose headphones, clone it and see what happens. If you're on another Bose model, the protocol documentation has everything you need to start mapping your device. The BMAP protocol is shared across Bose's Bluetooth product line — the architecture and likely the auth gaps are the same.

Your headphones. Your settings. Your call.
