import React from "react";
import { Composition } from "remotion";
import { ReelA_Split, ReelProps } from "./compositions/ReelA_Split";
import { ReelB_Phone } from "./compositions/ReelB_Phone";
import { ReelC_Chat } from "./compositions/ReelC_Chat";
import { PALETTES } from "./themes/palettes";

const defaultProps: ReelProps = {
  business: {
    name: "Apex Auto Care",
    vertical: "Auto Repair",
    city: "Pune",
    owner_name: "Rahul Sharma",
  },
  hook_text: "POV: You're under a car and a client calls to book brakes",
  audio_url: "",
  total_duration_seconds: 30,
  palette: PALETTES.midnight_indigo,
  caption_style: "word-highlight",
  words: [
    { word: "Thanks", start: 0.2, end: 0.5, speaker: "agent" },
    { word: "for", start: 0.5, end: 0.7, speaker: "agent" },
    { word: "calling", start: 0.7, end: 1.1, speaker: "agent" },
    { word: "Apex", start: 1.1, end: 1.5, speaker: "agent" },
    { word: "Auto.", start: 1.5, end: 1.9, speaker: "agent" },
    { word: "How", start: 2.1, end: 2.3, speaker: "agent" },
    { word: "can", start: 2.3, end: 2.5, speaker: "agent" },
    { word: "I", start: 2.5, end: 2.7, speaker: "agent" },
    { word: "help", start: 2.7, end: 3.0, speaker: "agent" },
    { word: "you", start: 3.0, end: 3.2, speaker: "agent" },
    { word: "today?", start: 3.2, end: 3.6, speaker: "agent" },
    { word: "Hi,", start: 4.0, end: 4.3, speaker: "caller" },
    { word: "I", start: 4.3, end: 4.5, speaker: "caller" },
    { word: "need", start: 4.5, end: 4.8, speaker: "caller" },
    { word: "a", start: 4.8, end: 5.0, speaker: "caller" },
    { word: "brake", start: 5.0, end: 5.3, speaker: "caller" },
    { word: "inspection", start: 5.3, end: 5.9, speaker: "caller" },
    { word: "tomorrow.", start: 5.9, end: 6.5, speaker: "caller" },
  ],
  events: [
    {
      turn_index: 2,
      time_seconds: 7.0,
      type: "tool_call",
      text: "Checking shop bay schedule...",
    },
    {
      turn_index: 3,
      time_seconds: 12.0,
      type: "booking_card",
      text: "Slot reserved: Tomorrow 3:30 PM",
    },
    {
      turn_index: 4,
      time_seconds: 18.0,
      type: "tool_call",
      text: "SMS confirmation & calendar invite sent",
    },
  ],
  amplitude_envelope: new Array(900).fill(0.2).map((_, i) => 0.15 + 0.35 * Math.sin(i * 0.1)),
  owner_notification: {
    summary: "New booking: Brake pad inspection for Honda City.",
    customer_name: "Vikram Malhotra",
    time_or_slot: "Tomorrow at 3:30 PM",
    service_requested: "Brake System Check",
    next_step: "Slot reserved in Bay 2.",
  },
  product: {
    name: "Vocalis AI",
    tagline: "Never miss a high-ticket customer call again.",
    cta_url: "vocalis.ai",
    cta_handle: "@vocalis.ai",
  },
};

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="ReelA-Split"
        component={ReelA_Split}
        durationInFrames={900}
        fps={30}
        width={1080}
        height={1920}
        defaultProps={defaultProps}
      />
      <Composition
        id="ReelB-Phone"
        component={ReelB_Phone}
        durationInFrames={900}
        fps={30}
        width={1080}
        height={1920}
        defaultProps={defaultProps}
      />
      <Composition
        id="ReelC-Chat"
        component={ReelC_Chat}
        durationInFrames={900}
        fps={30}
        width={1080}
        height={1920}
        defaultProps={defaultProps}
      />
    </>
  );
};
