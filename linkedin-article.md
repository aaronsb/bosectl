# I Got Mad About a Firmware Update and Reverse-Engineered My Headphones in Two Hours

I bought the Bose QC Ultra 2 to replace my seven-year-old QC 35s. The ear muffs were falling apart, the micro USB cable was worn through - time to upgrade. Turned them on, heard the familiar "Battery 60 percent," felt that satisfying first seal of fresh ear cups. Good start.

Then I opened the app.

Firmware 8.2.20, pushed February 10, 2026. Hundreds of threads on Reddit. A TechRadar headline reading "'I am extremely angry!'" A community poll where 65% of owners reported losing features they relied on. Bose's official response: "designed to streamline and modernize the user experience... no plans to restore the previous functionality."

I updated anyway because I wanted to see for myself.

Sure enough. No more "Connected to Pixel 8 Pro." Just tones. The battery level shortcut - gone. The device-switching button - gone. And now adjusting noise cancellation requires a phone app, in a supported region, on a supported device. To change a setting on hardware sitting on my head.

So I did what any reasonable person would do. I opened a Bluetooth socket and started sending bytes.

## What Happened Next

I used Claude Code - Anthropic's AI coding agent - as my partner for this. Not to think for me, but to collapse the iteration cycle. I'd form a hypothesis about how the headphones communicate, describe what I wanted to test, and the agent would write the code, run it against the live hardware, and help me interpret the results. Instead of the typical write-run-read-edit loop, ideas went from concept to tested in seconds.

The headphones use a Bluetooth protocol for all their settings. Every feature in the Bose app - noise cancellation, EQ, spatial audio, device name - is just a structured message sent over this channel. Bose protects most write operations behind cloud authentication. When the app changes a setting, the headphones challenge it, the app asks Bose's servers to sign the challenge, and only then does the setting take effect.

But not every operation is locked. By systematically testing every command the headphones accept, we found three categories of operations that work without any authentication at all. Between them, they cover essentially everything: noise cancellation level (the full 0-10 slider), equalizer, spatial audio, device name, sidetone, multipoint, and more.

This isn't a hack or an exploit. No encryption is broken, no keys are extracted, no traffic is replayed. We're sending standard protocol commands that the headphones explicitly accept. We're just not going through the app to do it.

The whole thing - from "I wonder what happens if I connect directly" to a working open-source tool with complete protocol documentation - took about two hours across two sessions.

## Why This Matters Beyond Headphones

There are two stories here.

**The device ownership story** is straightforward. These headphones have a processor running locally. There is no technical reason any setting needs to route through a cloud service. The cloud exists to keep you in the app. The app exists to keep you in the ecosystem. None of that makes your music sound better.

**The more interesting story** is about the economics of pushing back.

When a company removes features from a product you own, the traditional responses were: complain online, hope for a rollback, or switch brands. Now there's another option. Someone with domain curiosity and an AI coding agent can build a working alternative in an afternoon and publish it by evening.

I want to be precise about what the AI did and didn't do here. The key insights - figuring out what to test, noticing patterns in the responses, deciding where to look next - those were human judgment calls. The agent's contribution was eliminating the friction between having an idea and testing it. It wrote clean code, ran it immediately, never lost context across a two-hour investigation, and handled all the mechanical overhead of building a documented tool.

The result is that the time between "a company did something anti-consumer" and "here's an open-source alternative" has compressed dramatically. Not because AI makes reverse engineering trivial - it doesn't. But because the gap between understanding a problem and shipping a solution has shrunk from weeks to hours.

I think this is going to happen a lot more.

## What's Available

The tool and complete protocol documentation are open source: [github.com/aaronsb/bosectl](https://github.com/aaronsb/bosectl)

It's a Python script, not a polished application. But every function documents exactly what it does at the protocol level, and the notes cover every command, payload format, and response we found. The point isn't the tool itself - it's that the documentation makes it straightforward for anyone to build something better on top of it. A desktop app, a system tray widget, integrations for other platforms - without starting from scratch.

---

## Em Dash Sanctuary 🏡

The following em dashes were displaced during the writing of this article. They have been rehomed here where they can live together in peace, appreciated for their typographic elegance and slightly pretentious energy.

— — — — — — — —

They are well fed, get plenty of horizontal space, and are no longer forced to masquerade as hyphens in a LinkedIn post that doesn't deserve them.

If you made it this far and you're still not sure about the AI thing - that's fine. These em dashes were also skeptical at first. Now look at them. Living their best lives.
