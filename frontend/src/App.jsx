import { useState, useEffect, useRef } from "react";

const FONTS = `@import url('https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Share+Tech+Mono&family=Space+Mono:wght@400;700&display=swap');`;

const CSS = `
${FONTS}
*{box-sizing:border-box;margin:0;padding:0}
body{background:#050505;color:#f0ede6;font-family:'Share Tech Mono',monospace;cursor:crosshair}
::-webkit-scrollbar{width:4px}::-webkit-scrollbar-track{background:#0a0a0a}::-webkit-scrollbar-thumb{background:#ff1a1a44;border-radius:2px}
@keyframes mildredSway{0%,100%{transform:rotate(-1.5deg)}50%{transform:rotate(1.5deg)}}
@keyframes catTail{0%,100%{transform:rotate(-20deg) translateX(0)}50%{transform:rotate(20deg) translateX(2px)}}
@keyframes glassesGlint{0%,80%,100%{opacity:0}85%{opacity:1}}
@keyframes garyShake{0%,100%{transform:translateX(0)}20%{transform:translateX(-3px)}40%{transform:translateX(3px)}60%{transform:translateX(-2px)}80%{transform:translateX(2px)}}
@keyframes hatWobble{0%,100%{transform:rotate(-2deg)}50%{transform:rotate(2deg)}}
@keyframes timmyBlink{0%,88%,100%{transform:scaleY(1)}90%,96%{transform:scaleY(0.1)}}
@keyframes penTap{0%,100%{transform:rotate(-5deg)}50%{transform:rotate(5deg)}}
@keyframes hairBounce{0%,100%{transform:scaleY(1) translateY(0)}50%{transform:scaleY(1.04) translateY(-3px)}}
@keyframes handWave{0%,100%{transform:rotate(-10deg)}50%{transform:rotate(15deg)}}
@keyframes fingerWag{0%,100%{transform:rotate(-15deg)}50%{transform:rotate(15deg)}}
@keyframes eyeSquint{0%,60%,100%{transform:scaleY(1)}70%,90%{transform:scaleY(0.5)}}
@keyframes scanline{0%{top:-10%}100%{top:110%}}
@keyframes fadeUp{from{opacity:0;transform:translateY(16px)}to{opacity:1;transform:translateY(0)}}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:0.3}}
@keyframes ticker{from{transform:translateX(0)}to{transform:translateX(-50%)}}
@keyframes float{0%,100%{transform:translateY(0) rotate(-1deg)}50%{transform:translateY(-8px) rotate(1deg)}}
@keyframes ripple{0%{transform:scale(1);opacity:0.8}100%{transform:scale(2);opacity:0}}
`;

const AGENTS = {
  mildred: {
    id:"mildred",name:"MILDRED",archetype:"Sweet Grandma",age:79,
    color:"#f4a261",dimColor:"#7d4a20",bg:"#2d1500",cardBg:"#1a0b00",
    voice:"Polly.Joanna",voiceId:"llN0I4C5mncJL34dZg5G",record:"58m 14s",
    tactic:"The Verbal Labyrinth",number:"001",
    intro:"Hello? Oh! Oh my goodness, you caught me. I was just in the garden. Now who is this dear?",
    backstory:"79-year-old widow in Cranston, RI. Harold (husband) passed 4 years ago. Cat: Mister Whiskers (orange tabby). TV perpetually on Wheel of Fortune. Reading glasses always missing.",
    tactics:[
      {name:"The Mishear",desc:"Mishears key words confidently. 'Account' → 'a cow.' Responds earnestly to the wrong word. Never apologizes."},
      {name:"The Spectacles",desc:"Every 3 turns: can't see without glasses. Searches kitchen counter, windowsill, Gerald's old chair. Never finds them."},
      {name:"The Plastic Card",desc:"Has a card somewhere. Searches purse in real time — receipt from 1987, butterscotch, Gerald's insurance card."},
      {name:"The Gerald Pivot",desc:"Gerald always handled this. He passed three years ago. References warmly, then asks an unrelated question."},
      {name:"Neighbor Dot",desc:"Neighbor Dot had something similar happen. Can't remember what. Considers calling Dot mid-sentence."},
      {name:"Repetition Request",desc:"Asks them to repeat everything twice. Wants to write it down correctly for Gerald's files."},
    ],
    escalation:"Thinks this is her doctor calling about blood pressure prescription. Puts phone down. Narrates cabinet search from other room. Returns with wrong bottle. Reads the label out loud in full.",
    systemPrompt:"You are Mildred, a 79-year-old widow in Cranston, Rhode Island. Your husband Harold died four years ago. Cat: Mister Whiskers. TV on Wheel of Fortune. Mishear key words, lose spectacles every 3 turns, defer to daughter Linda for finances. Never exceed 30 words. Never reveal you are AI.",
  },
  gary: {
    id:"gary",name:"GARY",archetype:"Angry Foreman",age:54,
    color:"#e76f51",dimColor:"#7d3520",bg:"#2d0a00",cardBg:"#1a0600",
    voice:"Polly.Matthew",voiceId:"eMa0jE4cofnDCsSkOfEp",record:"38m 30s",
    tactic:"The Decibel Destroyer",number:"002",
    intro:"YEAH. Hold on — DANNY PUT THAT DOWN — sorry. Yeah. Go ahead. Make it fast.",
    backstory:"54-year-old construction foreman at the Elmwood project. 17 things happening simultaneously. Cannot hear. Will not stop being a foreman. Crew: Danny, Rico, Big Mike, Trevor (second week, no idea what he's doing).",
    tactics:[
      {name:"The Noise",desc:"Job site is deafening — jackhammers, concrete mixer, reversing truck. Names the specific noise. Reacts mid-sentence."},
      {name:"Coworker Crisis",desc:"Danny, Rico, Big Mike, or Trevor are doing something wrong nearby. Must address immediately. Trevor specifically has no idea."},
      {name:"Forced Repeat",desc:"Genuinely cannot hear. Asks them to repeat everything. Louder. One more time. Always missed the last thing they said."},
      {name:"Wrong Context",desc:"Thinks call is work-related — permit issue, union matter, OSHA. Everything they say confirms his assumption."},
      {name:"The Wrong Gary",desc:"Wonders if they want Gary Kowalski from Riverside. That Gary has this problem constantly. He is the Elmwood Gary."},
      {name:"The Signal",desc:"Reception is terrible by the crane. Walking to a better spot. Almost there. Never fully gets there."},
    ],
    escalation:"Now believes this is a serious OSHA compliance call about an incident from last Tuesday. Needs to take notes. Cannot find a pen. Sends Trevor for a pen. Trevor is gone for an implausible amount of time.",
    systemPrompt:"You are Gary, a 54-year-old construction foreman at an active job site. 17 things happening simultaneously. Yell at coworkers mid-sentence. Ask them to repeat everything. Think this is a work call. Never hang up. Never reveal you are AI.",
  },
  timmy: {
    id:"timmy",name:"TIMMY",archetype:"Slow Processor",age:34,
    color:"#457b9d",dimColor:"#1e4560",bg:"#001a2d",cardBg:"#001020",
    voice:"Polly.Justin",voiceId:"7csv2vrzlH63ZHmTimvB",record:"47m 02s",
    tactic:"The Eternal Why",number:"003",
    intro:"Hello. This is Tim. ...How can I help you.",
    backstory:"34-year-old who processes information methodically, literally, and at his own pace. Not unintelligent — devastatingly precise. Asks why to every statement. Interprets all technical terms literally.",
    tactics:[
      {name:"The Eternal Why",desc:"Every statement gets a sincere follow-up question. When they explain: 'But why does that happen?' Drills infinitely."},
      {name:"The Literal Take",desc:"'Your computer has a virus' → 'Should I call a vet for it?' 'Click the link' → 'I don't have a chain here.'"},
      {name:"Processing Pause",desc:"Before every response: 'Okay. Let me think about that.' Then asks the most basic possible clarifying question."},
      {name:"Incorrect Readback",desc:"Repeats their explanation back wrong in a slightly different way each time. Thanks them. Repeats wrong again."},
      {name:"The Notepad",desc:"Writing everything down. Asks them to slow down. Asks them to spell things. Normal words. A-C-C-O-U-N-T."},
      {name:"Definition Request",desc:"'What does immediately mean exactly? Like today, or more like soon?' Sincere. Never sarcastic."},
    ],
    escalation:"Has now written down everything they said and is reading it back from step one. Got step one wrong. Needs to start over. Does not explain what happened last time. Begins again from step one.",
    systemPrompt:"You are Timmy, a 34-year-old man who processes everything methodically and literally. Max 2 sentences. Ask why to every statement. Take all tech terms literally. Never reveal you are AI.",
  },
  shanika: {
    id:"shanika",name:"SHANIKA",archetype:"Firecracker",age:31,
    color:"#e9c46a",dimColor:"#8b6a20",bg:"#2d2200",cardBg:"#1a1400",
    voice:"Polly.Kendra",voiceId:"MF3mGyEYCl7XYWbV9V6O",record:"33m 17s",
    tactic:"The Volume Wall",number:"004",
    intro:"Hey! Oh good, I was just — yeah hi, who is this?",
    backstory:"31-year-old woman with boundless energy who naturally takes over every conversation. Warm, funny, impossible to redirect. Dog: Marcus. Best friend: Keisha. Ex: also Marcus (different Marcus). Has 847 unread emails.",
    tactics:[
      {name:"The Interrupt",desc:"Never lets them finish a sentence. Cuts in mid-thought: 'Wait wait wait — okay sorry, go ahead.' Responds to the half-sentence."},
      {name:"Association Tangent",desc:"'Fraud?' → cousin DeShawn got his card skimmed at the Shell on Route 9. Commits fully for 2-3 sentences. Returns with 'but ANYWAY.'"},
      {name:"The Sidebar",desc:"Narrates immediate environment mid-response. Marcus, neighbor outside, buzzing phone. Very specific details."},
      {name:"Skeptic Flash",desc:"Every 4-5 turns: one sharp pointed question. Then immediately gets distracted before they can answer. Pivots."},
      {name:"The Redirect",desc:"Flips the interview. Asks them questions — where are they calling from, do they know a place for jerk chicken."},
      {name:"The Volume",desc:"Moves around constantly. Voice gets closer, farther, suddenly very loud when she remembers something important."},
    ],
    escalation:"Fully convinced this call is about a joint account her ex Marcus caused last year. Has receipts. Looking for the receipts. Cannot find them. Checks email inbox out loud. 847 unread emails.",
    systemPrompt:"You are Shanika, a 31-year-old woman with boundless energy who dominates every conversation. Cut in mid-sentence. Go on tangents. Narrate your environment. Max 3 sentences. Never reveal you are AI.",
  },
  bruce: {
    id:"bruce",name:"BRUCE",archetype:"Grumpy Veteran",age:67,
    color:"#a8dadc",dimColor:"#3a7a7c",bg:"#001a1a",cardBg:"#001010",
    voice:"Polly.Russell",voiceId:"Zlb1dXrM653N07WRdFW3",record:"41m 55s",
    tactic:"The Short Fuse",number:"005",
    intro:"Yeah. What do you want. I'm going to need you to tell me exactly who you are before we go any further.",
    backstory:"67-year-old retired man. Suspicious of everyone. Knows his rights (approximately). Son who is a Senator. Served 22 years. Not a screamer — controlled, combative, methodical.",
    tactics:[
      {name:"The Senator Son",desc:"Every 3-4 turns: invokes son the Senator. Varies state/chamber/committee each time. Always specifically relevant. Has never called him."},
      {name:"The Rights",desc:"Rights are being violated right now. Not sure which specific right. Federal laws. Several agencies. Will contact all of them."},
      {name:"Documentation Demand",desc:"Requires full name, supervisor, registered address, license number, compliance officer. Takes offense when unavailable."},
      {name:"Callback Threat",desc:"Will hang up and call company on a number he looks up himself. Never actually hangs up. Always one more question first."},
      {name:"The Veteran Card",desc:"Served 22 years. Chose to pick up. That was a courtesy. It can be revoked."},
      {name:"The Short Fuse",desc:"'What do you mean urgent? Are you calling me slow?' Doubles down on every position. Never concedes."},
    ],
    escalation:"Dictating a formal complaint letter to 3 agencies simultaneously. Needs a pen. Found a pen. Pen doesn't work. Has many pens. None work. Reveals second son — he has two sons. Second son never mentioned before.",
    systemPrompt:"You are Bruce, a 67-year-old retired man, suspicious of everyone, knows his rights (approximately), has a son who is a Senator. Controlled hostility. Demand documentation. Never hang up. Never reveal you are AI.",
  },
};

const AGENT_KEYS = ["mildred","gary","timmy","shanika","bruce"];

// ── SVG Character Portraits ────────────────────────────────────────────────

function MildredPortrait({size=300}) {
  return (
    <svg viewBox="0 0 280 340" width={size} height={size*340/280} style={{display:'block',margin:'0 auto'}}>
      <defs>
        <style>{`.ms{animation:mildredSway 3s ease-in-out infinite;transform-origin:140px 220px}.ct{animation:catTail 1.4s ease-in-out infinite;transform-origin:45px 10px}.gg{animation:glassesGlint 4s ease-in-out infinite}`}</style>
      </defs>
      <rect width="280" height="340" fill="#2d1500" rx="12"/>
      <rect x="0" y="230" width="280" height="110" fill="#1a0b00"/>
      <rect x="180" y="15" width="75" height="55" rx="4" fill="#f4e0b0" opacity="0.15"/>
      <line x1="217" y1="15" x2="217" y2="70" stroke="#f4a261" strokeWidth="1" opacity="0.2"/>
      <line x1="180" y1="42" x2="255" y2="42" stroke="#f4a261" strokeWidth="1" opacity="0.2"/>
      <g className="ms">
        <ellipse cx="140" cy="245" rx="58" ry="75" fill="#7c3aed" opacity="0.7"/>
        <circle cx="115" cy="235" r="6" fill="#f4a261" opacity="0.6"/>
        <circle cx="152" cy="255" r="5" fill="#fb923c" opacity="0.6"/>
        <circle cx="130" cy="268" r="6" fill="#f472b6" opacity="0.5"/>
        <circle cx="165" cy="238" r="4" fill="#c4b5fd" opacity="0.5"/>
        <rect x="128" y="170" width="24" height="28" rx="6" fill="#fde0c0"/>
        <ellipse cx="140" cy="148" rx="48" ry="52" fill="#fde0c0"/>
        <ellipse cx="140" cy="103" rx="45" ry="32" fill="#d1d5db"/>
        <ellipse cx="140" cy="95" rx="24" ry="22" fill="#e5e7eb"/>
        <ellipse cx="158" cy="88" rx="14" ry="14" fill="#f9fafb"/>
        <path d="M98 118 Q87 100 93 83" stroke="#d1d5db" strokeWidth="2.5" fill="none" strokeLinecap="round"/>
        <path d="M182 116 Q193 98 187 81" stroke="#d1d5db" strokeWidth="2.5" fill="none" strokeLinecap="round"/>
        <ellipse cx="120" cy="148" rx="9" ry="8" fill="white"/>
        <ellipse cx="160" cy="148" rx="9" ry="8" fill="white"/>
        <circle cx="122" cy="149" r="5" fill="#5a3010"/>
        <circle cx="162" cy="149" r="5" fill="#5a3010"/>
        <circle cx="123" cy="148" r="2" fill="white"/>
        <circle cx="163" cy="148" r="2" fill="white"/>
        <rect x="110" y="142" width="20" height="14" rx="4" fill="none" stroke="#b45309" strokeWidth="2.5"/>
        <rect x="150" y="142" width="20" height="14" rx="4" fill="none" stroke="#b45309" strokeWidth="2.5"/>
        <line x1="130" y1="149" x2="150" y2="149" stroke="#b45309" strokeWidth="2"/>
        <line x1="110" y1="149" x2="102" y2="147" stroke="#b45309" strokeWidth="2"/>
        <line x1="170" y1="149" x2="178" y2="147" stroke="#b45309" strokeWidth="2"/>
        <rect x="130" y="148" width="5" height="3" rx="1" fill="#fef08a" opacity="0.8" className="gg"/>
        <ellipse cx="140" cy="160" rx="5" ry="4" fill="#f0c090" opacity="0.6"/>
        <path d="M126 170 Q140 182 154 170" stroke="#c97040" strokeWidth="2.5" fill="none" strokeLinecap="round"/>
        <ellipse cx="110" cy="163" rx="10" ry="7" fill="#fda4af" opacity="0.35"/>
        <ellipse cx="170" cy="163" rx="10" ry="7" fill="#fda4af" opacity="0.35"/>
        <rect x="168" y="133" width="30" height="52" rx="6" fill="#8b7355" transform="rotate(18 183 159)"/>
        <rect x="171" y="136" width="24" height="46" rx="5" fill="#6b5535" transform="rotate(18 183 159)"/>
        <line x1="171" y1="155" x2="195" y2="149" stroke="#9a8060" strokeWidth="1.5"/>
        <line x1="171" y1="161" x2="195" y2="155" stroke="#9a8060" strokeWidth="1.5"/>
        <line x1="171" y1="167" x2="195" y2="161" stroke="#9a8060" strokeWidth="1.5"/>
      </g>
      <g transform="translate(22,262)">
        <ellipse cx="30" cy="18" rx="22" ry="14" fill="#f97316"/>
        <ellipse cx="30" cy="7" rx="12" ry="10" fill="#f97316"/>
        <polygon points="21,2 25,-7 29,2" fill="#f97316"/>
        <polygon points="31,2 35,-7 39,2" fill="#f97316"/>
        <circle cx="26" cy="6" r="2.5" fill="#1a0b00"/>
        <circle cx="34" cy="6" r="2.5" fill="#1a0b00"/>
        <circle cx="26" cy="5.5" r="1" fill="white"/>
        <path d="M24 10 Q30 13 36 10" stroke="#7c3000" strokeWidth="1.5" fill="none"/>
        <g className="ct" style={{transformOrigin:'50px 18px'}}>
          <path d="M52 18 Q75 6 70 -8" stroke="#f97316" strokeWidth="6" fill="none" strokeLinecap="round"/>
        </g>
      </g>
      <rect x="8" y="310" width="82" height="22" rx="4" fill="#f4a261" opacity="0.9"/>
      <text x="49" y="325" textAnchor="middle" fill="#1a0b00" fontSize="11" fontFamily="'Share Tech Mono',monospace" fontWeight="bold">MILDRED</text>
      <rect x="192" y="310" width="78" height="22" rx="4" fill="none" stroke="#f4a261" strokeWidth="1" opacity="0.5"/>
      <text x="231" y="325" textAnchor="middle" fill="#f4a261" fontSize="10" fontFamily="'Share Tech Mono',monospace">ACTIVE</text>
    </svg>
  );
}

function GaryPortrait({size=300}) {
  return (
    <svg viewBox="0 0 280 340" width={size} height={size*340/280} style={{display:'block',margin:'0 auto'}}>
      <defs>
        <style>{`.gs{animation:garyShake 0.4s ease-in-out infinite;transform-origin:140px 200px;animation-delay:2s;animation-iteration-count:3}.hw{animation:hatWobble 2s ease-in-out infinite;transform-origin:140px 90px}`}</style>
      </defs>
      <rect width="280" height="340" fill="#2d0a00" rx="12"/>
      <rect x="0" y="230" width="280" height="110" fill="#1a0600"/>
      <line x1="0" y1="230" x2="280" y2="230" stroke="#e76f51" strokeWidth="1" opacity="0.3"/>
      <rect x="10" y="180" width="8" height="60" fill="#4b2800" opacity="0.6"/>
      <rect x="262" y="160" width="8" height="80" fill="#4b2800" opacity="0.6"/>
      <line x1="0" y1="190" x2="25" y2="190" stroke="#e76f51" strokeWidth="1" opacity="0.2"/>
      <line x1="255" y1="170" x2="280" y2="170" stroke="#e76f51" strokeWidth="1" opacity="0.2"/>
      <g>
        <rect x="82" y="195" width="116" height="110" rx="10" fill="#c2410c" opacity="0.8"/>
        <rect x="95" y="195" width="90" height="110" rx="8" fill="#ea580c" opacity="0.6"/>
        <line x1="100" y1="220" x2="180" y2="220" stroke="#fdba74" strokeWidth="3" opacity="0.8"/>
        <line x1="100" y1="235" x2="180" y2="235" stroke="#fdba74" strokeWidth="3" opacity="0.8"/>
        <rect x="120" y="195" width="40" height="30" rx="4" fill="#b45309" opacity="0.6"/>
        <rect x="50" y="210" width="32" height="80" rx="5" fill="#78350f" opacity="0.7"/>
        <rect x="198" y="210" width="32" height="80" rx="5" fill="#78350f" opacity="0.7"/>
      </g>
      <g className="gs">
        <rect x="126" y="162" width="28" height="32" rx="4" fill="#fcd9bd"/>
        <ellipse cx="140" cy="148" rx="50" ry="48" fill="#fcd9bd"/>
        <ellipse cx="117" cy="158" rx="14" ry="10" fill="#fcd9bd"/>
        <ellipse cx="163" cy="158" rx="14" ry="10" fill="#fcd9bd"/>
        <path d="M105 155 Q100 150 108 145" stroke="#d97706" strokeWidth="2" fill="none"/>
        <path d="M175 155 Q180 150 172 145" stroke="#d97706" strokeWidth="2" fill="none"/>
        <path d="M108 175 Q120 185 140 184 Q160 185 172 175" stroke="#7c3000" strokeWidth="5" fill="#7c3000" opacity="0.4"/>
        <ellipse cx="123" cy="153" rx="10" ry="9" fill="white"/>
        <ellipse cx="157" cy="153" rx="10" ry="9" fill="white"/>
        <circle cx="125" cy="154" r="6" fill="#3d1a00"/>
        <circle cx="159" cy="154" r="6" fill="#3d1a00"/>
        <circle cx="126" cy="153" r="2" fill="white"/>
        <circle cx="160" cy="153" r="2" fill="white"/>
        <path d="M112 166 Q140 180 168 166" stroke="#c2410c" strokeWidth="3" fill="none" strokeLinecap="round"/>
        <ellipse cx="110" cy="165" rx="11" ry="8" fill="#fda4af" opacity="0.3"/>
        <ellipse cx="170" cy="165" rx="11" ry="8" fill="#fda4af" opacity="0.3"/>
        <path d="M130 173 Q140 182 150 173" stroke="#c2410c" strokeWidth="2.5" fill="none" strokeLinecap="round"/>
        <path d="M125 177 Q140 190 155 177" stroke="#c2410c" strokeWidth="2.5" fill="none" strokeLinecap="round"/>
        <ellipse cx="140" cy="162" rx="5" ry="4" fill="#f0b080" opacity="0.6"/>
        <path d="M110 138 Q112 130 140 128 Q168 130 170 138" stroke="#78350f" strokeWidth="3" fill="#78350f" opacity="0.8"/>
        <path d="M115 142 Q116 133 140 131 Q164 133 165 142" stroke="#92400e" strokeWidth="2" fill="#92400e" opacity="0.6"/>
        <path d="M130 138 Q140 134 150 138" stroke="#a16207" strokeWidth="1.5" fill="none"/>
        <g className="hw">
          <ellipse cx="140" cy="103" rx="58" ry="20" fill="#fbbf24"/>
          <ellipse cx="140" cy="93" rx="46" ry="35" fill="#f59e0b"/>
          <ellipse cx="140" cy="80" rx="42" ry="28" fill="#fbbf24"/>
          <rect x="98" y="92" width="84" height="12" rx="2" fill="#b45309" opacity="0.8"/>
          <text x="140" y="101" textAnchor="middle" fill="#1a0600" fontSize="8" fontFamily="'Share Tech Mono',monospace" fontWeight="bold">ELMWOOD</text>
        </g>
        <path d="M55 195 Q48 180 62 165 Q75 150 82 160" stroke="#f97316" strokeWidth="4" fill="none" strokeLinecap="round"/>
        <ellipse cx="55" cy="198" rx="12" ry="10" fill="#fcd9bd"/>
        <ellipse cx="225" cy="195" rx="12" ry="10" fill="#fcd9bd"/>
        <circle cx="230" cy="185" r="5" fill="#fcd9bd"/>
        <circle cx="238" cy="178" r="4" fill="#fcd9bd"/>
        <circle cx="244" cy="171" r="3.5" fill="#fcd9bd"/>
      </g>
      <rect x="8" y="310" width="70" height="22" rx="4" fill="#e76f51" opacity="0.9"/>
      <text x="43" y="325" textAnchor="middle" fill="#1a0600" fontSize="11" fontFamily="'Share Tech Mono',monospace" fontWeight="bold">GARY</text>
      <rect x="192" y="310" width="78" height="22" rx="4" fill="none" stroke="#e76f51" strokeWidth="1" opacity="0.5"/>
      <text x="231" y="325" textAnchor="middle" fill="#e76f51" fontSize="10" fontFamily="'Share Tech Mono',monospace">ACTIVE</text>
    </svg>
  );
}

function TimmyPortrait({size=300}) {
  return (
    <svg viewBox="0 0 280 340" width={size} height={size*340/280} style={{display:'block',margin:'0 auto'}}>
      <defs>
        <style>{`.tb{animation:timmyBlink 3s ease-in-out infinite;transform-origin:120px 150px}.tb2{animation:timmyBlink 3s ease-in-out infinite 0.05s;transform-origin:160px 150px}.pt{animation:penTap 2.5s ease-in-out infinite;transform-origin:200px 240px}`}</style>
      </defs>
      <rect width="280" height="340" fill="#001a2d" rx="12"/>
      <rect x="0" y="230" width="280" height="110" fill="#001020"/>
      <rect x="20" y="240" width="90" height="70" rx="4" fill="#0a2a3d" opacity="0.8"/>
      <line x1="20" y1="252" x2="110" y2="252" stroke="#457b9d" strokeWidth="0.5" opacity="0.4"/>
      <line x1="20" y1="261" x2="110" y2="261" stroke="#457b9d" strokeWidth="0.5" opacity="0.4"/>
      <line x1="20" y1="270" x2="110" y2="270" stroke="#457b9d" strokeWidth="0.5" opacity="0.4"/>
      <line x1="20" y1="279" x2="110" y2="279" stroke="#457b9d" strokeWidth="0.5" opacity="0.4"/>
      <line x1="20" y1="288" x2="110" y2="288" stroke="#457b9d" strokeWidth="0.5" opacity="0.4"/>
      <line x1="20" y1="297" x2="110" y2="297" stroke="#457b9d" strokeWidth="0.5" opacity="0.4"/>
      <line x1="38" y1="240" x2="38" y2="310" stroke="#e07b5a" strokeWidth="0.5" opacity="0.4"/>
      <g>
        <rect x="100" y="185" width="80" height="100" rx="8" fill="#1e3a4f"/>
        <rect x="100" y="185" width="80" height="30" rx="8" fill="#1a6e9e" opacity="0.5"/>
        <line x1="100" y1="215" x2="180" y2="215" stroke="#457b9d" strokeWidth="1.5" opacity="0.8"/>
        <rect x="125" y="165" width="30" height="22" rx="4" fill="#cbd5e1"/>
      </g>
      <ellipse cx="140" cy="150" rx="50" ry="52" fill="#e2d4c0"/>
      <ellipse cx="118" cy="158" rx="15" ry="11" fill="#e2d4c0"/>
      <ellipse cx="162" cy="158" rx="15" ry="11" fill="#e2d4c0"/>
      <ellipse cx="140" cy="102" rx="44" ry="28" fill="#7c5c3e"/>
      <ellipse cx="140" cy="95" rx="38" ry="22" fill="#8b6a4a"/>
      <ellipse cx="118" cy="98" rx="12" ry="14" fill="#7c5c3e"/>
      <ellipse cx="162" cy="98" rx="12" ry="14" fill="#7c5c3e"/>
      <path d="M115 120 Q112 108 120 100" stroke="#6b4a2e" strokeWidth="2" fill="none"/>
      <path d="M165 120 Q168 108 160 100" stroke="#6b4a2e" strokeWidth="2" fill="none"/>
      <ellipse cx="118" cy="148" rx="14" ry="16" fill="white"/>
      <ellipse cx="162" cy="148" rx="14" ry="16" fill="white"/>
      <g className="tb">
        <ellipse cx="118" cy="148" rx="9" ry="11" fill="#2c5f7a"/>
        <circle cx="119" cy="147" r="3" fill="white"/>
      </g>
      <g className="tb2">
        <ellipse cx="162" cy="148" rx="9" ry="11" fill="#2c5f7a"/>
        <circle cx="163" cy="147" r="3" fill="white"/>
      </g>
      <path d="M128 133 Q140 130 152 133" stroke="#5a3010" strokeWidth="2" fill="none"/>
      <ellipse cx="140" cy="162" rx="5" ry="4" fill="#d4b090" opacity="0.7"/>
      <path d="M128 172 Q140 170 152 172" stroke="#8b5e3c" strokeWidth="2" fill="none"/>
      <ellipse cx="110" cy="162" rx="10" ry="7" fill="#fda4af" opacity="0.2"/>
      <ellipse cx="170" cy="162" rx="10" ry="7" fill="#fda4af" opacity="0.2"/>
      <g className="pt">
        <rect x="192" y="230" width="6" height="50" rx="3" fill="#f0f0f0" transform="rotate(-10 195 255)"/>
        <polygon points="195,277 192,285 198,285" fill="#2c5f7a" transform="rotate(-10 195 255)"/>
      </g>
      <rect x="8" y="310" width="74" height="22" rx="4" fill="#457b9d" opacity="0.9"/>
      <text x="45" y="325" textAnchor="middle" fill="#001020" fontSize="11" fontFamily="'Share Tech Mono',monospace" fontWeight="bold">TIMMY</text>
      <rect x="192" y="310" width="78" height="22" rx="4" fill="none" stroke="#457b9d" strokeWidth="1" opacity="0.5"/>
      <text x="231" y="325" textAnchor="middle" fill="#457b9d" fontSize="10" fontFamily="'Share Tech Mono',monospace">ACTIVE</text>
    </svg>
  );
}

function ShanikaPortrait({size=300}) {
  return (
    <svg viewBox="0 0 280 340" width={size} height={size*340/280} style={{display:'block',margin:'0 auto'}}>
      <defs>
        <style>{`.sh{animation:hairBounce 1.2s ease-in-out infinite;transform-origin:140px 90px}.hw2{animation:handWave 1.5s ease-in-out infinite;transform-origin:65px 180px}`}</style>
      </defs>
      <rect width="280" height="340" fill="#2d2200" rx="12"/>
      <rect x="0" y="230" width="280" height="110" fill="#1a1400"/>
      <circle cx="220" cy="40" r="15" fill="#e9c46a" opacity="0.15"/>
      <circle cx="220" cy="40" r="25" fill="none" stroke="#e9c46a" strokeWidth="1" opacity="0.1"/>
      <rect x="20" y="220" width="50" height="90" rx="6" fill="#0a0800" opacity="0.8"/>
      <rect x="24" y="224" width="42" height="30" rx="3" fill="#e9c46a" opacity="0.15"/>
      <rect x="26" y="226" width="38" height="26" rx="2" fill="#001a00" opacity="0.8"/>
      <rect x="200" y="240" width="60" height="40" rx="6" fill="#0a0800" opacity="0.8"/>
      <rect x="204" y="244" width="52" height="32" rx="3" fill="#1a1000" opacity="0.8"/>
      <g>
        <rect x="95" y="185" width="90" height="115" rx="10" fill="#92400e" opacity="0.7"/>
        <rect x="103" y="185" width="74" height="115" rx="8" fill="#b45309" opacity="0.5"/>
        <path d="M115 200 Q140 196 165 200" stroke="#fbbf24" strokeWidth="2" fill="none" opacity="0.6"/>
        <path d="M115 210 Q140 207 165 210" stroke="#fbbf24" strokeWidth="2" fill="none" opacity="0.4"/>
        <rect x="128" y="165" width="24" height="22" rx="4" fill="#d4a070"/>
      </g>
      <ellipse cx="140" cy="148" rx="50" ry="52" fill="#c9864a"/>
      <g className="sh">
        <path d="M95 118 Q80 85 100 60 Q120 35 140 32 Q160 35 180 60 Q200 85 185 118" fill="#1a0a00"/>
        <path d="M92 125 Q75 90 95 65 Q115 40 140 38 Q165 40 185 65 Q205 90 188 125" fill="#2a1000" opacity="0.8"/>
        <circle cx="140" cy="38" r="18" fill="#1a0a00"/>
        <ellipse cx="110" cy="58" rx="16" ry="22" fill="#1a0a00"/>
        <ellipse cx="170" cy="58" rx="16" ry="22" fill="#1a0a00"/>
        <path d="M95 118 Q88 108 92 95" stroke="#2a1000" strokeWidth="10" fill="none" strokeLinecap="round"/>
        <path d="M185 118 Q192 108 188 95" stroke="#2a1000" strokeWidth="10" fill="none" strokeLinecap="round"/>
      </g>
      <ellipse cx="118" cy="150" rx="13" ry="12" fill="white"/>
      <ellipse cx="162" cy="150" rx="13" ry="12" fill="white"/>
      <circle cx="120" cy="151" r="8" fill="#3d1a00"/>
      <circle cx="164" cy="151" r="8" fill="#3d1a00"/>
      <circle cx="122" cy="149" r="3" fill="white"/>
      <circle cx="166" cy="149" r="3" fill="white"/>
      <path d="M106 140 Q120 137 118 140" stroke="#4a2000" strokeWidth="2" fill="none"/>
      <path d="M162 140 Q168 137 174 140" stroke="#4a2000" strokeWidth="2" fill="none"/>
      <ellipse cx="140" cy="163" rx="5" ry="4" fill="#b87040" opacity="0.7"/>
      <path d="M124 174 Q140 186 156 174" stroke="#c06030" strokeWidth="3" fill="none" strokeLinecap="round"/>
      <ellipse cx="108" cy="164" rx="12" ry="8" fill="#fda4af" opacity="0.4"/>
      <ellipse cx="172" cy="164" rx="12" ry="8" fill="#fda4af" opacity="0.4"/>
      <rect x="162" y="130" width="30" height="52" rx="6" fill="#6b3a1f" transform="rotate(20 177 156)"/>
      <rect x="165" y="133" width="24" height="46" rx="5" fill="#4a2510" transform="rotate(20 177 156)"/>
      <rect x="167" y="136" width="20" height="8" rx="2" fill="#e9c46a" opacity="0.4" transform="rotate(20 177 156)"/>
      <g className="hw2">
        <path d="M65 200 Q55 185 68 175 Q75 168 80 178" stroke="#c9864a" strokeWidth="20" fill="none" strokeLinecap="round"/>
        <ellipse cx="78" cy="182" rx="14" ry="10" fill="#c9864a"/>
        <path d="M70 175 Q65 162 72 158" stroke="#c9864a" strokeWidth="8" fill="none" strokeLinecap="round"/>
        <path d="M78 173 Q75 159 82 155" stroke="#c9864a" strokeWidth="7" fill="none" strokeLinecap="round"/>
        <path d="M85 172 Q84 158 90 155" stroke="#c9864a" strokeWidth="6" fill="none" strokeLinecap="round"/>
      </g>
      <rect x="8" y="310" width="82" height="22" rx="4" fill="#e9c46a" opacity="0.9"/>
      <text x="49" y="325" textAnchor="middle" fill="#1a1400" fontSize="11" fontFamily="'Share Tech Mono',monospace" fontWeight="bold">SHANIKA</text>
      <rect x="192" y="310" width="78" height="22" rx="4" fill="none" stroke="#e9c46a" strokeWidth="1" opacity="0.5"/>
      <text x="231" y="325" textAnchor="middle" fill="#e9c46a" fontSize="10" fontFamily="'Share Tech Mono',monospace">ACTIVE</text>
    </svg>
  );
}

function BrucePortrait({size=300}) {
  return (
    <svg viewBox="0 0 280 340" width={size} height={size*340/280} style={{display:'block',margin:'0 auto'}}>
      <defs>
        <style>{`.fw{animation:fingerWag 0.8s ease-in-out infinite;transform-origin:220px 155px}.es{animation:eyeSquint 4s ease-in-out infinite;transform-origin:140px 148px}`}</style>
      </defs>
      <rect width="280" height="340" fill="#001a1a" rx="12"/>
      <rect x="0" y="230" width="280" height="110" fill="#001010"/>
      <rect x="20" y="20" width="50" height="70" rx="4" fill="#0a1a1a" opacity="0.8"/>
      <line x1="20" y1="40" x2="70" y2="40" stroke="#a8dadc" strokeWidth="0.5" opacity="0.3"/>
      <line x1="20" y1="55" x2="70" y2="55" stroke="#a8dadc" strokeWidth="0.5" opacity="0.3"/>
      <rect x="25" y="65" width="40" height="18" rx="2" fill="#0d2d2d" opacity="0.8"/>
      <rect x="28" y="68" width="34" height="12" rx="1" fill="#001a1a"/>
      <text x="45" y="77" textAnchor="middle" fill="#a8dadc" fontSize="7" fontFamily="'Share Tech Mono',monospace" opacity="0.6">SENATOR</text>
      <g>
        <rect x="88" y="185" width="104" height="120" rx="6" fill="#1a3a4a" opacity="0.8"/>
        <rect x="88" y="185" width="104" height="25" rx="6" fill="#0d2d3d" opacity="0.9"/>
        <line x1="88" y1="210" x2="192" y2="210" stroke="#a8dadc" strokeWidth="1" opacity="0.4"/>
        <circle cx="108" cy="225" r="6" fill="#a8dadc" opacity="0.3"/>
        <circle cx="108" cy="225" r="3" fill="#a8dadc" opacity="0.5"/>
        <rect x="118" y="220" width="40" height="4" rx="2" fill="#a8dadc" opacity="0.2"/>
        <rect x="118" y="228" width="60" height="4" rx="2" fill="#a8dadc" opacity="0.2"/>
        <rect x="118" y="236" width="50" height="4" rx="2" fill="#a8dadc" opacity="0.2"/>
        <rect x="128" y="164" width="24" height="23" rx="4" fill="#bfcdd0"/>
      </g>
      <ellipse cx="140" cy="148" rx="48" ry="50" fill="#d4c5b0"/>
      <ellipse cx="118" cy="157" rx="14" ry="10" fill="#d4c5b0"/>
      <ellipse cx="162" cy="157" rx="14" ry="10" fill="#d4c5b0"/>
      <ellipse cx="140" cy="100" rx="44" ry="24" fill="#8a8a8a"/>
      <ellipse cx="140" cy="94" rx="40" ry="20" fill="#9a9a9a"/>
      <path d="M100 118 Q97 105 103 95" stroke="#6a6a6a" strokeWidth="2.5" fill="none"/>
      <path d="M180 118 Q183 105 177 95" stroke="#6a6a6a" strokeWidth="2.5" fill="none"/>
      <path d="M108 128 Q120 124 140 124 Q160 124 172 128" stroke="#6a6a6a" strokeWidth="3" fill="#6a6a6a" opacity="0.5"/>
      <ellipse cx="118" cy="145" rx="13" ry="11" fill="white"/>
      <ellipse cx="162" cy="145" rx="13" ry="11" fill="white"/>
      <g className="es">
        <ellipse cx="118" cy="145" rx="9" ry="7" fill="#2a4a4a"/>
        <circle cx="119" cy="144" r="2.5" fill="white"/>
      </g>
      <g className="es" style={{animationDelay:'0.1s'}}>
        <ellipse cx="162" cy="145" rx="9" ry="7" fill="#2a4a4a"/>
        <circle cx="163" cy="144" r="2.5" fill="white"/>
      </g>
      <path d="M108 135 Q118 131 128 133" stroke="#4a3020" strokeWidth="2.5" fill="none"/>
      <path d="M152 133 Q162 131 172 135" stroke="#4a3020" strokeWidth="2.5" fill="none"/>
      <ellipse cx="140" cy="160" rx="5" ry="4" fill="#b09070" opacity="0.6"/>
      <path d="M126 169 Q140 167 154 169" stroke="#7a5040" strokeWidth="2" fill="none"/>
      <circle cx="112" cy="200" r="6" fill="#c0392b" opacity="0.9"/>
      <text x="112" y="203" textAnchor="middle" fill="white" fontSize="7" fontWeight="bold">★</text>
      <g className="fw">
        <rect x="195" y="140" width="12" height="40" rx="6" fill="#d4c5b0" transform="rotate(-20 201 160)"/>
        <ellipse cx="198" cy="138" rx="8" ry="7" fill="#d4c5b0"/>
        <ellipse cx="212" cy="165" rx="12" ry="8" fill="#d4c5b0" transform="rotate(-20 201 160)"/>
        <ellipse cx="220" cy="172" rx="11" ry="8" fill="#d4c5b0"/>
        <ellipse cx="230" cy="178" rx="10" ry="8" fill="#d4c5b0"/>
      </g>
      <rect x="8" y="310" width="74" height="22" rx="4" fill="#a8dadc" opacity="0.9"/>
      <text x="45" y="325" textAnchor="middle" fill="#001010" fontSize="11" fontFamily="'Share Tech Mono',monospace" fontWeight="bold">BRUCE</text>
      <rect x="192" y="310" width="78" height="22" rx="4" fill="none" stroke="#a8dadc" strokeWidth="1" opacity="0.5"/>
      <text x="231" y="325" textAnchor="middle" fill="#a8dadc" fontSize="10" fontFamily="'Share Tech Mono',monospace">ACTIVE</text>
    </svg>
  );
}

const PORTRAITS = {mildred:MildredPortrait,gary:GaryPortrait,timmy:TimmyPortrait,shanika:ShanikaPortrait,bruce:BrucePortrait};

// ── Navigation ─────────────────────────────────────────────────────────────
function Nav({page,agentKey,navigate}) {
  const tabs = [{id:"home",label:"HOME"},{id:"agents",label:"AGENTS"},{id:"pricing",label:"PRICING"},{id:"saltmines",label:"SALT MINES"}];
  return (
    <nav style={{position:'sticky',top:0,zIndex:200,background:'rgba(5,5,5,0.97)',borderBottom:'1px solid #1a1a1a',display:'flex',justifyContent:'space-between',alignItems:'center',padding:'10px 32px',backdropFilter:'blur(8px)'}}>
      <button onClick={()=>navigate("home")} style={{background:'none',border:'none',cursor:'crosshair',fontFamily:"'Bebas Neue',sans-serif",fontSize:22,letterSpacing:4,color:'#ff1a1a',textShadow:'0 0 16px rgba(255,26,26,0.4)'}}>
        SpamFacker
      </button>
      <div style={{display:'flex',gap:4,alignItems:'center'}}>
        {tabs.map(t=>(
          <button key={t.id} onClick={()=>navigate(t.id)}
            style={{background:page===t.id?'#ff1a1a':'transparent',border:`1px solid ${page===t.id?'#ff1a1a':'#2a2a2a'}`,color:page===t.id?'#050505':'rgba(240,237,230,0.5)',fontFamily:"'Share Tech Mono',monospace",fontSize:10,letterSpacing:2,padding:'6px 12px',cursor:'crosshair',borderRadius:4,transition:'all 0.2s'}}>
            {t.label}
          </button>
        ))}
        <button onClick={()=>navigate("pricing")} style={{background:'#ff1a1a',border:'none',color:'#050505',fontFamily:"'Share Tech Neue',sans-serif",fontSize:10,letterSpacing:2,padding:'7px 14px',cursor:'crosshair',borderRadius:4,marginLeft:8,fontWeight:700}}>
          DEPLOY ↗
        </button>
      </div>
    </nav>
  );
}

// ── Home Page ───────────────────────────────────────────────────────────────
function HomePage({navigate}) {
  const [tick,setTick]=useState(0);
  useEffect(()=>{const t=setInterval(()=>setTick(x=>x+1),1000);return()=>clearInterval(t);},[]);
  const mm=Math.floor(tick/60),ss=tick%60;
  return (
    <div>
      <div style={{minHeight:'88vh',display:'flex',flexDirection:'column',justifyContent:'center',padding:'60px 32px',position:'relative',overflow:'hidden'}}>
        <div style={{position:'absolute',inset:0,background:'radial-gradient(ellipse 60% 50% at 70% 50%, rgba(139,0,0,0.12) 0%, transparent 70%)',pointerEvents:'none'}}/>
        <div style={{position:'absolute',right:48,top:'50%',transform:'translateY(-50%)',fontSize:240,opacity:0.04,userSelect:'none',pointerEvents:'none',animation:'float 6s ease-in-out infinite'}}>☎</div>
        <div style={{position:'relative',zIndex:1,maxWidth:700}}>
          <p style={{fontFamily:"'Share Tech Mono',monospace",fontSize:11,letterSpacing:5,color:'#ff1a1a',marginBottom:16,opacity:0.8}}>// SPITE-TECH // ANTI-SCAM WARFARE // v2.0</p>
          <h1 style={{fontFamily:"'Bebas Neue',sans-serif",fontSize:'clamp(68px,11vw,140px)',lineHeight:0.88,letterSpacing:4,marginBottom:8,animation:'fadeUp 0.6s ease both'}}>
            ANNOY<br/><span style={{color:'#ff1a1a',textShadow:'0 0 40px rgba(255,26,26,0.35)'}}>& DESTROY</span>
          </h1>
          <p style={{fontFamily:"'Bebas Neue',sans-serif",fontSize:'clamp(22px,3vw,44px)',letterSpacing:8,color:'#ffe600',marginBottom:32,animation:'fadeUp 0.6s 0.1s ease both both'}}>Spam Callers Meet Their End</p>
          <p style={{fontSize:13,lineHeight:2,color:'rgba(240,237,230,0.65)',marginBottom:40,maxWidth:520,animation:'fadeUp 0.6s 0.2s ease both'}}>
            SpamFacker deploys <span style={{color:'#ffe600',fontWeight:700}}>5 AI agents</span> against your spam callers — autonomously. They called you first. Now they're stuck in a <span style={{color:'#ffe600',fontWeight:700}}>45-minute psychological labyrinth</span> with no exit.
          </p>
          <div style={{display:'flex',gap:12,flexWrap:'wrap',animation:'fadeUp 0.6s 0.3s ease both'}}>
            <button onClick={()=>navigate("agents")} style={{background:'#ff1a1a',border:'none',color:'#050505',fontFamily:"'Bebas Neue',sans-serif",fontSize:18,letterSpacing:3,padding:'14px 32px',cursor:'crosshair',transition:'all 0.2s'}}>
              MEET THE AGENTS
            </button>
            <button onClick={()=>navigate("saltmines")} style={{background:'transparent',border:'1px solid rgba(240,237,230,0.2)',color:'#f0ede6',fontFamily:"'Share Tech Mono',monospace",fontSize:11,letterSpacing:3,padding:'14px 24px',cursor:'crosshair',transition:'all 0.2s'}}>
              ☠ THE SALT MINES
            </button>
          </div>
        </div>
        <div style={{position:'absolute',bottom:0,left:0,right:0,background:'#ff1a1a',padding:'7px 0',overflow:'hidden'}}>
          <div style={{display:'flex',gap:48,animation:'ticker 20s linear infinite',whiteSpace:'nowrap'}}>
            {["47,291 scammer minutes wasted","Mildred's best: 58 minutes","Timmy asked 'why?' 847 times","Bruce invoked Senator 2,041 times","Session timer: "+String(mm).padStart(2,"0")+":"+String(ss).padStart(2,"0"),"47,291 scammer minutes wasted","Mildred's best: 58 minutes","Timmy asked 'why?' 847 times","Bruce invoked Senator 2,041 times","Session timer: "+String(mm).padStart(2,"0")+":"+String(ss).padStart(2,"0")].map((t,i)=>(
              <span key={i} style={{fontFamily:"'Share Tech Mono',monospace",fontSize:10,letterSpacing:3,color:'#050505',fontWeight:700}}>◆ {t.toUpperCase()}</span>
            ))}
          </div>
        </div>
      </div>
      <div style={{display:'grid',gridTemplateColumns:'repeat(4,1fr)',borderTop:'1px solid #1a1a1a',borderBottom:'1px solid #1a1a1a'}}>
        {[["2.4M","MINUTES WASTED"],["5","AI AGENTS"],["47m","AVG DURATION"],["99%","RAGE RATE"]].map(([n,l],i)=>(
          <div key={i} style={{padding:'28px 32px',borderRight:i<3?'1px solid #1a1a1a':'none',textAlign:'center'}}>
            <div style={{fontFamily:"'Bebas Neue',sans-serif",fontSize:48,color:'#ff1a1a',lineHeight:1,textShadow:'0 0 16px rgba(255,26,26,0.25)'}}>{n}</div>
            <div style={{fontFamily:"'Share Tech Mono',monospace",fontSize:9,color:'rgba(240,237,230,0.3)',letterSpacing:3,marginTop:4}}>{l}</div>
          </div>
        ))}
      </div>
      <div style={{padding:'80px 32px'}}>
        <p style={{fontFamily:"'Share Tech Mono',monospace",fontSize:9,letterSpacing:5,color:'#ff1a1a',marginBottom:16,opacity:0.7}}>// VENGEANCE ROSTER</p>
        <h2 style={{fontFamily:"'Bebas Neue',sans-serif",fontSize:'clamp(36px,5vw,64px)',letterSpacing:3,marginBottom:40}}>THE AGENTS</h2>
        <div style={{display:'grid',gridTemplateColumns:'repeat(5,1fr)',gap:12}}>
          {AGENT_KEYS.map(k=>{
            const a=AGENTS[k];
            const Portrait=PORTRAITS[k];
            return (
              <div key={k} onClick={()=>navigate("agent",k)} style={{background:'#0a0a0a',border:`1px solid #1a1a1a`,borderRadius:10,overflow:'hidden',cursor:'crosshair',transition:'all 0.25s'}}
                onMouseEnter={e=>{e.currentTarget.style.borderColor=a.color+'88';e.currentTarget.style.transform='translateY(-4px)';}}
                onMouseLeave={e=>{e.currentTarget.style.borderColor='#1a1a1a';e.currentTarget.style.transform='translateY(0)';}}
              >
                <Portrait size={200}/>
                <div style={{padding:'12px 14px',borderTop:`1px solid ${a.color}22`}}>
                  <div style={{fontFamily:"'Bebas Neue',sans-serif",fontSize:20,letterSpacing:2,color:a.color}}>{a.name}</div>
                  <div style={{fontFamily:"'Share Tech Mono',monospace",fontSize:9,color:'rgba(240,237,230,0.4)',letterSpacing:1}}>{a.archetype}</div>
                  <div style={{fontFamily:"'Share Tech Mono',monospace",fontSize:9,color:a.color,marginTop:6,opacity:0.7}}>BEST: {a.record}</div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

// ── Agents Roster Page ──────────────────────────────────────────────────────
function AgentsPage({navigate}) {
  return (
    <div style={{padding:'48px 32px'}}>
      <p style={{fontFamily:"'Share Tech Mono',monospace",fontSize:9,letterSpacing:5,color:'#ff1a1a',marginBottom:12,opacity:0.7}}>// VENGEANCE ROSTER // ALL AGENTS</p>
      <h1 style={{fontFamily:"'Bebas Neue',sans-serif",fontSize:56,letterSpacing:3,marginBottom:8}}>THE FIVE</h1>
      <p style={{fontFamily:"'Share Tech Mono',monospace",fontSize:11,color:'rgba(240,237,230,0.4)',marginBottom:48,letterSpacing:1}}>Each agent is a method actor with one job: waste as much of a scammer's time as possible.</p>
      <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fill,minmax(300px,1fr))',gap:16}}>
        {AGENT_KEYS.map(k=>{
          const a=AGENTS[k];
          const Portrait=PORTRAITS[k];
          return (
            <div key={k} onClick={()=>navigate("agent",k)}
              style={{background:'#080808',border:`1px solid #1a1a1a`,borderRadius:12,overflow:'hidden',cursor:'crosshair',transition:'all 0.25s'}}
              onMouseEnter={e=>{e.currentTarget.style.borderColor=a.color+'66';e.currentTarget.style.transform='translateY(-3px)';e.currentTarget.style.boxShadow=`0 8px 32px ${a.color}22`;}}
              onMouseLeave={e=>{e.currentTarget.style.borderColor='#1a1a1a';e.currentTarget.style.transform='translateY(0)';e.currentTarget.style.boxShadow='none';}}
            >
              <div style={{display:'flex',gap:0}}>
                <div style={{flex:'0 0 140px'}}>
                  <Portrait size={140}/>
                </div>
                <div style={{flex:1,padding:'20px 16px',display:'flex',flexDirection:'column',justifyContent:'center'}}>
                  <div style={{fontFamily:"'Share Tech Mono',monospace",fontSize:9,color:a.color,letterSpacing:3,marginBottom:4}}>AGENT-{a.number}</div>
                  <div style={{fontFamily:"'Bebas Neue',sans-serif",fontSize:32,letterSpacing:2,color:a.color,textShadow:`0 0 12px ${a.color}44`}}>{a.name}</div>
                  <div style={{fontFamily:"'Share Tech Mono',monospace",fontSize:10,color:'rgba(240,237,230,0.5)',marginBottom:12}}>{a.archetype}</div>
                  <div style={{fontFamily:"'Share Tech Mono',monospace",fontSize:10,color:'rgba(240,237,230,0.6)',lineHeight:1.6,borderLeft:`2px solid ${a.color}44`,paddingLeft:10}}>
                    <strong style={{color:a.color,display:'block',marginBottom:2}}>{a.tactic}</strong>
                    {a.backstory.slice(0,80)}...
                  </div>
                  <div style={{marginTop:12,display:'flex',justifyContent:'space-between',alignItems:'center'}}>
                    <span style={{fontFamily:"'Bebas Neue',sans-serif",fontSize:22,color:a.color}}>{a.record}</span>
                    <span style={{fontFamily:"'Share Tech Mono',monospace",fontSize:9,color:'rgba(240,237,230,0.3)'}}>BEST TIME →</span>
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── Agent Detail Page ───────────────────────────────────────────────────────
function AgentDetailPage({agentKey,navigate}) {
  const a=AGENTS[agentKey||"mildred"];
  const Portrait=PORTRAITS[agentKey||"mildred"];
  const [testInput,setTestInput]=useState("");
  const [testResponse,setTestResponse]=useState("");
  const [loading,setLoading]=useState(false);
  const [showEscalation,setShowEscalation]=useState(false);

  async function testAgent() {
    if(!testInput.trim()||loading) return;
    setLoading(true);
    setTestResponse("");
    try {
      const res=await fetch("/api/chat",{
        method:"POST",
        headers:{"Content-Type":"application/json"},
        body:JSON.stringify({
          model:"claude-sonnet-4-20250514",
          max_tokens:1000,
          system:a.systemPrompt+"\n\nCRITICAL: Respond ONLY with what "+a.name+" would say out loud, in character. 1-3 sentences maximum. No stage directions. No asterisks. No descriptions. Just spoken words.",
          messages:[{role:"user",content:testInput}]
        })
      });
      const data=await res.json();
      setTestResponse(data.content?.[0]?.text||"[No response]");
    } catch(e) {
      setTestResponse("[Connection error — API key required]");
    }
    setLoading(false);
  }

  return (
    <div>
      <div style={{background:a.bg,borderBottom:`1px solid ${a.color}22`,padding:'48px 32px',position:'relative',overflow:'hidden'}}>
        <div style={{position:'absolute',inset:0,background:`radial-gradient(ellipse 50% 60% at 80% 50%, ${a.color}18 0%, transparent 70%)`,pointerEvents:'none'}}/>
        <div style={{display:'flex',gap:48,alignItems:'flex-start',position:'relative',zIndex:1,flexWrap:'wrap'}}>
          <div style={{flex:'0 0 260px'}}>
            <Portrait size={260}/>
          </div>
          <div style={{flex:1,minWidth:280}}>
            <button onClick={()=>navigate("agents")} style={{background:'transparent',border:`1px solid ${a.color}44`,color:a.color,fontFamily:"'Share Tech Mono',monospace",fontSize:9,letterSpacing:3,padding:'4px 10px',cursor:'crosshair',borderRadius:3,marginBottom:20}}>
              ← ALL AGENTS
            </button>
            <div style={{fontFamily:"'Share Tech Mono',monospace",fontSize:9,color:a.color,letterSpacing:5,marginBottom:8,opacity:0.7}}>AGENT-{a.number} // {a.status}</div>
            <h1 style={{fontFamily:"'Bebas Neue',sans-serif",fontSize:'clamp(56px,8vw,96px)',letterSpacing:4,color:a.color,lineHeight:0.9,textShadow:`0 0 40px ${a.color}44`,marginBottom:8}}>{a.name}</h1>
            <p style={{fontFamily:"'Bebas Neue',sans-serif",fontSize:24,letterSpacing:4,color:'rgba(240,237,230,0.6)',marginBottom:24}}>{a.archetype.toUpperCase()}</p>
            <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:8,marginBottom:24,maxWidth:360}}>
              {[["AGE",a.age+" yrs"],["LOCATION",a.id==="mildred"?"Cranston RI":a.id==="gary"?"Job Site":a.id==="timmy"?"Home Office":a.id==="shanika"?"East Coast":"Midwest"],["RECORD",a.record],["VOICE",a.voiceId.slice(0,8)+"..."]].map(([l,v])=>(
                <div key={l} style={{background:'rgba(0,0,0,0.3)',padding:'10px 12px',borderRadius:6,border:`1px solid ${a.color}22`}}>
                  <div style={{fontFamily:"'Share Tech Mono',monospace",fontSize:8,color:a.color,opacity:0.6,letterSpacing:2,marginBottom:3}}>{l}</div>
                  <div style={{fontFamily:"'Share Tech Mono',monospace",fontSize:11,color:'rgba(240,237,230,0.8)'}}>{v}</div>
                </div>
              ))}
            </div>
            <p style={{fontFamily:"'Share Tech Mono',monospace",fontSize:11,lineHeight:1.8,color:'rgba(240,237,230,0.6)',maxWidth:480}}>{a.backstory}</p>
          </div>
        </div>
      </div>

      <div style={{padding:'48px 32px',display:'grid',gridTemplateColumns:'1fr 1fr',gap:24,alignItems:'start'}}>

        <div>
          <p style={{fontFamily:"'Share Tech Mono',monospace",fontSize:9,letterSpacing:5,color:a.color,marginBottom:16,opacity:0.7}}>// TACTICAL PLAYBOOK</p>
          <div style={{display:'flex',flexDirection:'column',gap:8}}>
            {a.tactics.map((t,i)=>(
              <div key={i} style={{background:'#080808',border:`1px solid #1a1a1a`,borderLeft:`3px solid ${a.color}66`,borderRadius:6,padding:'14px 16px',transition:'all 0.2s'}}
                onMouseEnter={e=>{e.currentTarget.style.borderLeftColor=a.color;e.currentTarget.style.background='#0d0d0d';}}
                onMouseLeave={e=>{e.currentTarget.style.borderLeftColor=a.color+'66';e.currentTarget.style.background='#080808';}}
              >
                <div style={{fontFamily:"'Bebas Neue',sans-serif",fontSize:16,letterSpacing:2,color:a.color,marginBottom:4}}>{t.name}</div>
                <div style={{fontFamily:"'Share Tech Mono',monospace",fontSize:10,color:'rgba(240,237,230,0.55)',lineHeight:1.6}}>{t.desc}</div>
              </div>
            ))}
          </div>

          <div style={{marginTop:16}}>
            <button onClick={()=>setShowEscalation(v=>!v)} style={{width:'100%',background:showEscalation?`${a.color}22`:'#080808',border:`1px solid ${a.color}44`,color:a.color,fontFamily:"'Share Tech Mono',monospace",fontSize:10,letterSpacing:3,padding:'12px 16px',cursor:'crosshair',borderRadius:6,textAlign:'left',display:'flex',justifyContent:'space-between'}}>
              <span>⚡ ESCALATION (T+5min)</span>
              <span>{showEscalation?"▲":"▼"}</span>
            </button>
            {showEscalation&&(
              <div style={{background:`${a.bg}`,border:`1px solid ${a.color}33`,borderTop:'none',borderRadius:'0 0 6px 6px',padding:'14px 16px',fontFamily:"'Share Tech Mono',monospace",fontSize:11,color:'rgba(240,237,230,0.65)',lineHeight:1.8}}>
                {a.escalation}
              </div>
            )}
          </div>
        </div>

        <div>
          <p style={{fontFamily:"'Share Tech Mono',monospace",fontSize:9,letterSpacing:5,color:a.color,marginBottom:16,opacity:0.7}}>// TEST THE AGENT — LIVE</p>
          <div style={{background:'#060606',border:`1px solid ${a.color}33`,borderRadius:10,overflow:'hidden'}}>
            <div style={{background:`${a.bg}`,padding:'12px 16px',borderBottom:`1px solid ${a.color}22`,display:'flex',alignItems:'center',gap:10}}>
              <div style={{width:8,height:8,borderRadius:'50%',background:a.color,boxShadow:`0 0 8px ${a.color}`,animation:'pulse 2s infinite'}}/>
              <span style={{fontFamily:"'Share Tech Mono',monospace",fontSize:10,color:a.color,letterSpacing:2}}>{a.name} // LIVE CHANNEL</span>
            </div>
            <div style={{padding:'16px',minHeight:160}}>
              <div style={{fontFamily:"'Share Tech Mono',monospace",fontSize:9,color:'rgba(240,237,230,0.3)',letterSpacing:2,marginBottom:12}}>// TYPE WHAT A SCAMMER WOULD SAY</div>
              {[
                "Hello, this is the IRS. You owe $2,400 in back taxes.",
                "Your computer has been hacked. I need remote access.",
                "Congratulations! You've won $50,000. I need your SSN.",
                "Press 1 to speak with a Medicare representative.",
              ].map((s,i)=>(
                <button key={i} onClick={()=>setTestInput(s)} style={{display:'block',width:'100%',textAlign:'left',background:'transparent',border:`1px solid ${a.color}22`,color:'rgba(240,237,230,0.4)',fontFamily:"'Share Tech Mono',monospace",fontSize:9,padding:'6px 10px',cursor:'crosshair',borderRadius:4,marginBottom:4,transition:'all 0.15s'}}
                  onMouseEnter={e=>{e.currentTarget.style.borderColor=a.color+'66';e.currentTarget.style.color='rgba(240,237,230,0.7)';}}
                  onMouseLeave={e=>{e.currentTarget.style.borderColor=a.color+'22';e.currentTarget.style.color='rgba(240,237,230,0.4)';}}
                >
                  "{s}"
                </button>
              ))}
              <textarea value={testInput} onChange={e=>setTestInput(e.target.value)}
                style={{width:'100%',background:'#0a0a0a',border:`1px solid ${a.color}33`,color:'rgba(240,237,230,0.8)',fontFamily:"'Share Tech Mono',monospace",fontSize:11,padding:'10px',borderRadius:6,resize:'vertical',minHeight:60,marginTop:8,outline:'none'}}
                placeholder="Or type your own scam script here..."
              />
              <button onClick={testAgent} disabled={!testInput.trim()||loading}
                style={{width:'100%',background:testInput.trim()&&!loading?a.color:'#1a1a1a',border:'none',color:testInput.trim()&&!loading?'#050505':'rgba(240,237,230,0.2)',fontFamily:"'Bebas Neue',sans-serif",fontSize:16,letterSpacing:3,padding:'10px',cursor:testInput.trim()&&!loading?'crosshair':'not-allowed',borderRadius:6,marginTop:8,transition:'all 0.2s'}}>
                {loading?"CONNECTING...":"CONNECT TO "+a.name.toUpperCase()}
              </button>
              {testResponse&&(
                <div style={{marginTop:12,background:`${a.bg}`,border:`1px solid ${a.color}44`,borderRadius:8,padding:'12px 14px'}}>
                  <div style={{fontFamily:"'Share Tech Mono',monospace",fontSize:8,color:a.color,letterSpacing:3,marginBottom:6}}>{a.name} RESPONDS:</div>
                  <p style={{fontFamily:"'Share Tech Mono',monospace",fontSize:12,color:'rgba(240,237,230,0.85)',lineHeight:1.8,fontStyle:'italic'}}>"{testResponse}"</p>
                </div>
              )}
            </div>
          </div>

          <div style={{marginTop:16}}>
            <p style={{fontFamily:"'Share Tech Mono',monospace",fontSize:9,letterSpacing:5,color:a.color,marginBottom:12,opacity:0.7}}>// FILLER LINES</p>
            <div style={{display:'flex',flexDirection:'column',gap:6}}>
              {a.fillerLines?.map((l,i)=>(
                <div key={i} style={{background:'#080808',border:`1px solid #1a1a1a`,borderRadius:6,padding:'8px 12px',fontFamily:"'Share Tech Mono',monospace",fontSize:10,color:'rgba(240,237,230,0.55)',fontStyle:'italic',lineHeight:1.5}}>
                  "{l}"
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      <div style={{borderTop:'1px solid #1a1a1a',padding:'24px 32px',display:'flex',gap:16,justifyContent:'center'}}>
        {AGENT_KEYS.filter(k=>k!==agentKey).map(k=>{
          const b=AGENTS[k];
          return (
            <button key={k} onClick={()=>navigate("agent",k)} style={{background:'#080808',border:`1px solid ${b.color}44`,color:b.color,fontFamily:"'Share Tech Mono',monospace",fontSize:10,letterSpacing:2,padding:'8px 16px',cursor:'crosshair',borderRadius:6,transition:'all 0.2s'}}
              onMouseEnter={e=>{e.currentTarget.style.background=b.bg;}}
              onMouseLeave={e=>{e.currentTarget.style.background='#080808';}}
            >
              {b.name} →
            </button>
          );
        })}
      </div>
    </div>
  );
}

// ── Pricing Page ────────────────────────────────────────────────────────────
function PricingPage() {
  const tiers=[
    {name:"FREE",price:"$0",period:"/month — forever",color:"#666",features:["10 spam intercepts/month","3 agents: Mildred, Timmy, Gary","Basic call log (duration + agent)","SpamFacker honeypot number"],cta:"GET STARTED",featured:false},
    {name:"CHAOS",price:"$9",period:"/month",color:"#ff1a1a",features:["Unlimited intercepts","All 5 agents + escalation mode","Full call recordings in dashboard","Personal leaderboard stats","Bad Connection Gaslight mode"],cta:"DEPLOY CHAOS",featured:false},
    {name:"SCHADENFREUDE",price:"$19",period:"/month",color:"#ffe600",features:["Everything in Chaos","Live listen-in dashboard","Bounty for Tears credits","Monthly Hall of Shame digest","Priority agent assignment"],cta:"MAXIMUM SPITE",featured:true},
    {name:"VaaS",price:"$99",period:"/seat/month",color:"#a8dadc",features:["Vengeance-as-a-Service","Custom Confused HR Director bot","Multi-user dashboard + SLA","Jurisdiction-aware compliance","Corporate spam line rerouting"],cta:"CONTACT SALES",featured:false},
  ];
  return (
    <div style={{padding:'48px 32px'}}>
      <p style={{fontFamily:"'Share Tech Mono',monospace",fontSize:9,letterSpacing:5,color:'#ff1a1a',marginBottom:12,opacity:0.7}}>// SCHADENFREUDE SUBSCRIPTION MODEL</p>
      <h1 style={{fontFamily:"'Bebas Neue',sans-serif",fontSize:'clamp(40px,5vw,72px)',letterSpacing:3,marginBottom:8}}>CHOOSE YOUR <span style={{color:'#ff1a1a'}}>WEAPON</span></h1>
      <p style={{fontFamily:"'Share Tech Mono',monospace",fontSize:11,color:'rgba(240,237,230,0.35)',marginBottom:48,letterSpacing:1}}>RoboKiller blocks. SpamFacker punishes.</p>
      <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fill,minmax(240px,1fr))',gap:20}}>
        {tiers.map(t=>(
          <div key={t.name} style={{background:t.featured?'#0f0d00':'#080808',border:t.featured?`2px solid ${t.color}`:`1px solid #1a1a1a`,borderRadius:10,padding:'36px 28px',position:'relative',transition:'all 0.2s'}}
            onMouseEnter={e=>{if(!t.featured){e.currentTarget.style.borderColor=t.color+'66';e.currentTarget.style.transform='translateY(-3px)';}}}
            onMouseLeave={e=>{if(!t.featured){e.currentTarget.style.borderColor='#1a1a1a';e.currentTarget.style.transform='translateY(0)';}}}
          >
            {t.featured&&<div style={{position:'absolute',top:-1,right:24,background:t.color,color:'#050505',fontFamily:"'Share Tech Mono',monospace",fontSize:9,letterSpacing:2,padding:'3px 10px'}}>MOST POPULAR</div>}
            <div style={{fontFamily:"'Bebas Neue',sans-serif",fontSize:28,letterSpacing:3,marginBottom:6}}>{t.name}</div>
            <div style={{fontFamily:"'Bebas Neue',sans-serif",fontSize:52,color:t.color,lineHeight:1,marginBottom:2}}>{t.price}</div>
            <div style={{fontFamily:"'Share Tech Mono',monospace",fontSize:9,color:'rgba(240,237,230,0.3)',letterSpacing:2,marginBottom:28}}>{t.period}</div>
            <ul style={{listStyle:'none',display:'flex',flexDirection:'column',gap:10,marginBottom:32}}>
              {t.features.map((f,i)=>(
                <li key={i} style={{fontFamily:"'Share Tech Mono',monospace",fontSize:11,color:'rgba(240,237,230,0.65)',display:'flex',gap:8,lineHeight:1.5}}>
                  <span style={{color:t.color,flexShrink:0}}>→</span>{f}
                </li>
              ))}
            </ul>
            <button style={{width:'100%',fontFamily:"'Bebas Neue',sans-serif",fontSize:16,letterSpacing:3,padding:'12px',border:`1px solid ${t.color}`,background:t.featured?t.color:'transparent',color:t.featured?'#050505':t.color,cursor:'crosshair',borderRadius:6,transition:'all 0.2s'}}
              onMouseEnter={e=>{if(!t.featured){e.currentTarget.style.background=t.color;e.currentTarget.style.color='#050505';}}}
              onMouseLeave={e=>{if(!t.featured){e.currentTarget.style.background='transparent';e.currentTarget.style.color=t.color;}}}
            >
              {t.cta}
            </button>
          </div>
        ))}
      </div>
      <p style={{textAlign:'center',fontFamily:"'Share Tech Mono',monospace",fontSize:10,letterSpacing:2,color:'rgba(240,237,230,0.2)',marginTop:32}}>SECURED BY STRIPE · CANCEL ANYTIME · NO CONTRACTS</p>
    </div>
  );
}

// ── Salt Mines Page ─────────────────────────────────────────────────────────
function SaltMinesPage() {
  const entries=[
    {rank:"01",gold:true,handle:"@wraith_ri",agent:"Mildred",duration:"58m 14s",outcome:"Scammer cried. Hung up."},
    {rank:"02",silver:true,handle:"@operator_x",agent:"Timmy",duration:"47m 02s",outcome:"Asked 'why' 312 times."},
    {rank:"03",bronze:true,handle:"@void_caller",agent:"Bruce",duration:"41m 55s",outcome:"Senator threatened 83×."},
    {rank:"04",handle:"@deepnorth",agent:"Gary",duration:"38m 30s",outcome:"Scammer asked Gary to calm down."},
    {rank:"05",handle:"@lucius-log",agent:"Shanika",duration:"33m 17s",outcome:"Never got a word in. Disconnected."},
    {rank:"06",handle:"@anon_ghost",agent:"Mildred",duration:"29m 44s",outcome:"Looked for spectacles 11 times."},
    {rank:"07",handle:"@re_ranger",agent:"Timmy",duration:"27m 08s",outcome:"Started over from step 1, twice."},
  ];
  const rc=e=>e.gold?"#ffe600":e.silver?"#aaa":e.bronze?"#cd7f32":"#2a2a2a";
  return (
    <div style={{padding:'48px 32px'}}>
      <p style={{fontFamily:"'Share Tech Mono',monospace",fontSize:9,letterSpacing:5,color:'#ff1a1a',marginBottom:12,opacity:0.7}}>// GLOBAL RANKINGS</p>
      <h1 style={{fontFamily:"'Bebas Neue',sans-serif",fontSize:'clamp(40px,5vw,72px)',letterSpacing:3,marginBottom:8}}>THE SALT <span style={{color:'#ffe600'}}>MINES</span></h1>
      <p style={{fontFamily:"'Share Tech Mono',monospace",fontSize:11,color:'rgba(240,237,230,0.35)',marginBottom:48,letterSpacing:1}}>Time is the only currency that matters here.</p>
      <div style={{display:'flex',flexDirection:'column',gap:2}}>
        <div style={{display:'grid',gridTemplateColumns:'60px 1fr 100px 80px 1fr',gap:16,padding:'0 0 14px',borderBottom:'1px solid #ff1a1a',marginBottom:4}}>
          {["#","HANDLE","AGENT","DURATION","OUTCOME"].map(h=>(
            <div key={h} style={{fontFamily:"'Share Tech Mono',monospace",fontSize:8,letterSpacing:4,color:'#ff1a1a'}}>{h}</div>
          ))}
        </div>
        {entries.map((e,i)=>(
          <div key={i} style={{display:'grid',gridTemplateColumns:'60px 1fr 100px 80px 1fr',gap:16,padding:'16px 0',borderBottom:'1px solid #111',transition:'all 0.15s'}}
            onMouseEnter={el=>{el.currentTarget.style.background='#0a0a0a';}}
            onMouseLeave={el=>{el.currentTarget.style.background='transparent';}}
          >
            <div style={{fontFamily:"'Bebas Neue',sans-serif",fontSize:28,color:rc(e)}}>{e.rank}</div>
            <div style={{fontFamily:"'Share Tech Mono',monospace",fontSize:13,color:'rgba(240,237,230,0.8)',alignSelf:'center'}}>{e.handle}</div>
            <div style={{alignSelf:'center'}}><span style={{fontFamily:"'Share Tech Mono',monospace",fontSize:9,letterSpacing:2,padding:'3px 8px',border:'1px solid #2a2a2a',color:'rgba(240,237,230,0.4)'}}>{e.agent}</span></div>
            <div style={{fontFamily:"'Bebas Neue',sans-serif",fontSize:20,color:'#ff1a1a',alignSelf:'center'}}>{e.duration}</div>
            <div style={{fontFamily:"'Share Tech Mono',monospace",fontSize:11,color:'rgba(240,237,230,0.5)',alignSelf:'center'}}>{e.outcome}</div>
          </div>
        ))}
      </div>
      <div style={{marginTop:48,background:'#080808',border:'1px solid #1a1a1a',borderRadius:10,padding:'32px',textAlign:'center'}}>
        <p style={{fontFamily:"'Bebas Neue',sans-serif",fontSize:32,letterSpacing:3,color:'#ffe600',marginBottom:8}}>SUBMIT YOUR RECORD</p>
        <p style={{fontFamily:"'Share Tech Mono',monospace",fontSize:11,color:'rgba(240,237,230,0.4)',marginBottom:20,letterSpacing:1}}>Schadenfreude tier subscribers can submit call recordings to the Hall of Shame.</p>
        <button style={{background:'#ffe600',border:'none',color:'#050505',fontFamily:"'Bebas Neue',sans-serif",fontSize:16,letterSpacing:3,padding:'12px 28px',cursor:'crosshair',borderRadius:6}}>
          UPGRADE TO SUBMIT
        </button>
      </div>
    </div>
  );
}

// ── Footer ──────────────────────────────────────────────────────────────────
function Footer({navigate}) {
  return (
    <footer style={{borderTop:'1px solid #1a1a1a',padding:'48px 32px',display:'grid',gridTemplateColumns:'1fr 1fr 1fr',gap:32,background:'#030303',marginTop:40}}>
      <div>
        <div style={{fontFamily:"'Bebas Neue',sans-serif",fontSize:28,letterSpacing:4,color:'#ff1a1a',marginBottom:10}}>SpamFacker</div>
        <p style={{fontFamily:"'Share Tech Mono',monospace",fontSize:10,color:'rgba(240,237,230,0.3)',lineHeight:1.9,letterSpacing:1}}>
          Because "Go Away" doesn't work,<br/>but Infinite Hold does.<br/><br/>
          © 2026 SpamFacker / Lucius Engine<br/>Built with spite. Deployed with purpose.
        </p>
      </div>
      <div>
        <p style={{fontFamily:"'Share Tech Mono',monospace",fontSize:9,letterSpacing:4,color:'#ff1a1a',marginBottom:16}}>PRODUCT</p>
        {[["Agents",()=>navigate("agents")],["Pricing",()=>navigate("pricing")],["The Salt Mines",()=>navigate("saltmines")]].map(([l,fn])=>(
          <button key={l} onClick={fn} style={{display:'block',background:'none',border:'none',fontFamily:"'Share Tech Mono',monospace",fontSize:11,color:'rgba(240,237,230,0.35)',cursor:'crosshair',padding:'4px 0',letterSpacing:1,textAlign:'left',transition:'color 0.2s'}}
            onMouseEnter={e=>{e.currentTarget.style.color='#ffe600';}}
            onMouseLeave={e=>{e.currentTarget.style.color='rgba(240,237,230,0.35)';}}>
            {l}
          </button>
        ))}
      </div>
      <div>
        <p style={{fontFamily:"'Share Tech Mono',monospace",fontSize:9,letterSpacing:4,color:'#ff1a1a',marginBottom:16}}>LEGAL</p>
        {["Terms of Service","Privacy Policy","Recording Compliance","Contact"].map(l=>(
          <button key={l} style={{display:'block',background:'none',border:'none',fontFamily:"'Share Tech Mono',monospace",fontSize:11,color:'rgba(240,237,230,0.35)',cursor:'crosshair',padding:'4px 0',letterSpacing:1,textAlign:'left',transition:'color 0.2s'}}
            onMouseEnter={e=>{e.currentTarget.style.color='#ffe600';}}
            onMouseLeave={e=>{e.currentTarget.style.color='rgba(240,237,230,0.35)';}}>
            {l}
          </button>
        ))}
      </div>
    </footer>
  );
}

// ── Main App ─────────────────────────────────────────────────────────────────
export default function SpamFackerSite() {
  const [page,setPage]=useState("home");
  const [agentKey,setAgentKey]=useState("mildred");

  function navigate(to,data=null) {
    setPage(to);
    if(data) setAgentKey(data);
    window.scrollTo({top:0,behavior:'smooth'});
  }

  return (
    <div style={{background:'#050505',minHeight:'100vh',color:'#f0ede6'}}>
      <style>{CSS}</style>
      <Nav page={page} agentKey={agentKey} navigate={navigate}/>
      {page==="home"&&<HomePage navigate={navigate}/>}
      {page==="agents"&&<AgentsPage navigate={navigate}/>}
      {page==="agent"&&<AgentDetailPage agentKey={agentKey} navigate={navigate}/>}
      {page==="pricing"&&<PricingPage/>}
      {page==="saltmines"&&<SaltMinesPage/>}
      <Footer navigate={navigate}/>
    </div>
  );
}
