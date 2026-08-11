"""
In Time Television - Series Bible & Episode Generator
Generates the series bible, season arcs, and episode scripts for the
"In Time" television series, inspired by the film "In Time" (2011).

The series expands the film's universe into 8 seasons x 16 episodes = 128 episodes.
Each episode is 45 minutes (2700 seconds).

Series Bible includes:
- World rules and mechanics
- Character profiles
- Season arcs
- Episode breakdowns
"""

SERIES_BIBLE = {
    "title": "In Time Television",
    "concept": (
        "In a future where the human aging gene has been deactivated and time has become "
        "the universal currency, the rich can live forever while the poor fight for every "
        "second. The series follows those who dare to challenge the system, exploring themes "
        "of inequality, immortality, rebellion, and what it truly means to be alive."
    ),
    "description": (
        "Set 50 years after the events of the film, the time-is-money system has evolved. "
        "New zones have been established, the resistance has fractured, and a new generation "
        "of time-runners, time-thieves, and time-keepers navigate a world where every second "
        "counts - literally. The series explores the human cost of immortality, the economics "
        "of time, and the fragile line between revolution and terrorism."
    ),
    "genre": "sci-fi",
    "target_episode_duration": 2700,
    "seasons_planned": 8,
    "episodes_per_season": 16,
    "world_bible": """
# IN TIME TELEVISION - WORLD BIBLE

## THE WORLD

### Timeline
- Year 2169: The aging gene is deactivated. Humans stop aging at 25.
- Year 2170: Time becomes currency. Everyone is genetically engineered to live to 70.
- Year 2175: Time Zones established - Dayton (poorest) to New Greenwich (richest)
- Year 2210: The Will Salas Rebellion (events of the film)
- Year 2215: The System Reformation - surface changes, same inequality
- Year 2260: PRESENT DAY - The New Zones, expanded world, deeper divides

### Time Zones (Present Day)
1. **Dayton Zone** - Poorest. People live day-to-day. Minimum wage: 2 hours/day. Life expectancy: 27
2. **Paco Zone** - Working class. Factory workers, service industry. Min wage: 8 hours/day
3. **Marshall Zone** - Middle class. Skilled labor, small business. Comfortable but precarious
4. **Greenwich Prime** - Wealthy. Old money, executives. Centuries of time banked
5. **New Greenwich Elite** - Ultra-rich. Millennia of time. Effectively immortal
6. **The Fringe** - Lawless zones outside the system. Time-thieves, runners, outcasts

### How Time Works
- Everyone's forearm displays a living clock. Green = time remaining. Red = running out.
- At 25, the clock starts ticking down from 1 year. You must earn time to live.
- Time is transferred via skin contact (arm to arm)
- Time can be stored in "time capsules" (physical storage devices)
- "Timing out" = death. Your clock hits zero, you die instantly.
- "Clearing" = stealing someone's time by force (arm lock, draining)
- Time-keepers = police who enforce time laws and zone boundaries
- Time-banks = institutions that loan time at predatory rates

### Key Rules
- Crossing zones costs time (tolls). Dayton to Greenwich: 2 months toll
- "Time caps" prevent inflation - no one can hold more than 10,000 years
- The "Millennium Clause" - those who reach 1000 years get special privileges
- "Time sharing" is illegal in most zones (considered socialism)
- Black market time trading exists in The Fringe
- "Time ghosts" - people who have lived so long they've forgotten their original identity

## THEMES
- Economic inequality as literal life-or-death
- The psychological cost of immortality
- Revolution vs. terrorism - where's the line?
- Love and relationships when time is finite/infinite
- Corporate control of life itself
- The meaning of mortality and why it matters
""",
    "characters": {
        "kai_morrow": {
            "name": "Kai Morrow",
            "description": "A 26-year-old time-runner from Dayton who discovers a conspiracy that could collapse the entire time economy.",
            "appearance": "Lean, athletic build from years of running. Dark brown skin, close-cropped hair, intense amber eyes that seem to calculate every second. Wears worn clothes with hidden time capsule pockets. A faint scar on his left forearm from a near-timing-out experience.",
            "personality": "Resourceful, quick-thinking, distrustful of authority. Deeply empathetic despite a hard exterior. Haunted by watching his mother time out when he was 19. Driven by a need to find meaning in a world that measures life in seconds.",
            "background": "Born in Dayton. Mother was a factory worker who timed out when Kai was 19. Father unknown. Raised by the community. Became a time-runner (smuggling time across zones) at 21. Has never had more than 3 days of time at once.",
            "voice_profile": "Low, measured, with a Dayton accent. Speaks economically - never wastes words."
        },
        "sable_cross": {
            "name": "Sable Cross",
            "description": "A time-keeper captain in Marshall Zone who begins to question the system she's sworn to protect.",
            "appearance": "Tall, striking, mixed-race woman appearing 25 (actually 87). Sharp features, dark hair pulled back in a tight bun. Wears the crisp black uniform of a time-keeper with a silver time-keeper's badge. Her eyes carry the weight of decades she doesn't look old enough to have lived.",
            "personality": "Disciplined, principled, increasingly conflicted. Believes in order but beginning to see the system's cruelty. Struggles with having arrested people who then timed out in holding.",
            "background": "Born in Marshall Zone to a time-keeper family. Joined the academy at 25 (when her clock started). Has been a time-keeper for 62 years. Has 40 years banked - comfortable but not rich. Never married - 'relationships are a luxury.'",
            "voice_profile": "Clear, commanding, with a slight Marshall Zone polish. Becomes quieter when conflicted."
        },
        "orion_vex": {
            "name": "Orion Vex",
            "description": "A centuries-old time dealer in The Fringe who knows where the bodies are buried.",
            "appearance": "Appears 25, actually 340 years old. Pale skin, silver-white hair (dyed - a Fringe fashion statement). Wears layered, eclectic clothing from different decades he's lived through. Multiple time capsules strapped to his body. A knowing, world-weary smile.",
            "personality": "Charming, amoral, surprisingly wise. Has seen empires rise and fall. Deals time to survive but has a code: never deals to kids, never clears. Secretly funds resistance cells.",
            "background": "Originally from Greenwich Prime. Inherited millennia of time. Grew bored with immortality, gave most away, moved to The Fringe. Has been a dealer, a revolutionary, a hermit, and a philosopher across his 340 years. Knew Will Salas personally.",
            "voice_profile": "Smooth, theatrical, with an accent that shifts between zones. Occasionally uses phrases from centuries past."
        },
        "director_chen": {
            "name": "Director Chen",
            "description": "The head of the Time Authority, who controls the global time economy from New Greenwich.",
            "appearance": "Appears 25, actually 156. East Asian features, impeccable suits worth decades of time. Cold, precise movements. A digital clock on his desk that shows his personal time: 8,432 years. Wears a silver ring that's actually a master time capsule.",
            "personality": "Calculating, patient, genuinely believes the system prevents chaos. Views time inequality as natural law, not injustice. Willing to sacrifice individuals for 'stability.' Not evil - terrifyingly rational.",
            "background": "Born in Greenwich Prime. Trained as an economist. Rose through the Time Authority by solving 'time crises' (mass timing-outs in poor zones). Believes he's saving more lives than he takes.",
            "voice_profile": "Calm, precise, never raises his voice. Speaks in measured, economic terms."
        },
        "mira_santos": {
            "name": "Mira Santos",
            "description": "A young hacker from Paco Zone who can manipulate time displays and transfer systems.",
            "appearance": "19 years old (clock hasn't started yet - 6 years until it does). Small, wiry, dark curly hair always in a mess. Wears oversized hoodies with modified tech hidden inside. Bright, quick eyes. Always fidgeting with a small time-display device she's hacked.",
            "personality": "Brilliant, rebellious, reckless. Hacks for fun and principle. Doesn't fully grasp the danger she's in because she hasn't started her clock yet. Sees the system as a puzzle to solve.",
            "background": "Born in Paco Zone. Parents are factory workers. Self-taught programmer. Discovered she could manipulate time-transfer signals at 16. Has been secretly redistributing small amounts of time in her community.",
            "voice_profile": "Fast, excited, uses tech jargon. Gets quieter when scared."
        }
    },
    "season_arcs": {
        "1": {
            "title": "The Discovery",
            "arc": "Kai discovers a hidden algorithm in the time system that's deliberately accelerating timing-outs in poor zones to maintain the time economy. He must gather allies, evade time-keepers, and decide whether to expose the truth or use it for personal gain.",
            "episodes": 16
        },
        "2": {
            "title": "The Fracture",
            "arc": "The revelation causes social upheaval. The resistance splits between reformers and revolutionaries. Sable must choose sides. Orion's past catches up with him.",
            "episodes": 16
        },
        "3": {
            "title": "The War",
            "arc": "Open conflict between zones. Time-keepers vs. time-runners. Mira's hacks become weapons. Director Chen launches a counter-operation.",
            "episodes": 16
        },
        "4": {
            "title": "The Price",
            "arc": "The consequences of revolution. Friends become enemies. Kai must face what he's become. The system fights back with a new technology that can remotely drain time.",
            "episodes": 16
        },
        "5": {
            "title": "The Underground",
            "arc": "The resistance goes deep underground. New characters emerge from The Fringe. A parallel time economy is built. Orion reveals a secret from the original Will Salas rebellion.",
            "episodes": 16
        },
        "6": {
            "title": "The Reckoning",
            "arc": "Director Chen's true plan is revealed - a 'Great Reset' that would redistribute all time equally, but at a terrible cost. Kai and Sable must work together for the first time.",
            "episodes": 16
        },
        "7": {
            "title": "The New World",
            "arc": "After the Great Reset, a new world emerges. But human nature hasn't changed. New inequalities form. The question becomes: was any of it worth it?",
            "episodes": 16
        },
        "8": {
            "title": "The Last Second",
            "arc": "Final season. The system faces total collapse. Kai must make the ultimate choice - save the system that killed his mother, or let it all burn. The series finale answers whether time should ever be currency.",
            "episodes": 16
        }
    }
}

# Episode 1 Script - "Tick"
EPISODE_1_SCRIPT = """
TITLE: Tick
SEASON 1, EPISODE 1
TARGET DURATION: 45 minutes

SYNOPSIS: In Dayton Zone, Kai Morrow lives day-to-day, literally. When a stranger 
gives him a century of time before timing out, Kai's life is transformed. But the 
Time Authority wants that time back, and a time-keeper named Sable Cross is 
assigned to find him. Meanwhile, in The Fringe, an old dealer named Orion Vex 
watches the news with knowing eyes.

===

SCENE 1 - INT. DAYTON APARTMENT - DAWN

Kai wakes up to the sound of his forearm alarm. He looks at his clock: 19:14:33. 
Nineteen hours, fourteen minutes, thirty-three seconds. Less than a day to live.

He gets up in a cramped, dim apartment. The walls are thin - he can hear neighbors 
coughing, arguing, a baby crying. The room is sparse: a mattress, a small table, 
a worn jacket hanging on a nail.

Kai looks at a faded photograph on the wall - his mother, smiling. Her clock 
reads 00:00:00 in the photo. He touches it briefly, then turns away.

He puts on his jacket, checks his time again: 19:12:08. He pauses, takes a breath, 
and walks out the door.

SCENE 2 - EXT. DAYTON STREETS - MORNING

Dayton Zone. The streets are crowded, dirty, alive with desperation. People walk 
fast - not because they're in a hurry, but because every second matters. Digital 
billboards flash time prices: "BREAD: 45 MINUTES" "WATER: 12 MINUTES" "BUS FARE: 
30 MINUTES."

Kai walks through the crowd. A TIME BEGGAR sits against a wall, his clock at 
00:02:14. He reaches out to passersby. Most look away. Kai pauses, looks at the 
man, looks at his own clock (19:08:22), and keeps walking. He can't afford to help.

A TIME-KEEPER patrols the street in a black uniform. People give him a wide berth. 
His eyes scan the crowd, looking for anyone with too much time - a sign of theft.

Kai enters a factory building. Above the door, a sign reads: "DAYTON PROCESSING - 
SHIFT WORK: 8 HOURS FOR 2 HOURS."

SCENE 3 - INT. DAYTON PROCESSING FACTORY - DAY

Inside the factory, hundreds of workers sit at conveyor belts, assembling time 
capsule components. The work is repetitive, mindless, exhausting. A DIGITAL CLOCK 
on the wall shows everyone's shift time counting down.

Kai sits at his station. His neighbor, an older man named TOBY (appears 25, 
actually 45), leans over.

TOBY: You look worse than usual.

KAI: Didn't sleep.

TOBY: None of us sleep. That's the point.

Kai manages a thin smile. He works. The camera lingers on his hands, his clock, 
the clock on the wall. Time is literally being converted into labor.

A SUPERVISOR walks by, checking output rates.

SUPERVISOR: Morrow. You're behind. Pick it up or I'm docking 30 minutes.

Kai works faster. His clock ticks: 18:47:12.

SCENE 4 - EXT. DAYTON STREET CORNER - EVENING

After work. Kai's clock reads 20:31:45 - he earned just over an hour for a full 
shift. He buys a food packet (15 minutes) and eats it walking.

He passes a bar called "THE LAST SECOND." Through the window, he sees people 
drinking, laughing, gambling with time. A CARD GAME is in progress - players 
betting minutes and hours.

Kai considers going in, but checks his time: 20:16:33. He can't afford to gamble. 
He keeps walking.

SCENE 5 - EXT. DAYTON ALLEY - NIGHT

Kai takes a shortcut through a narrow alley. Halfway through, he hears a sound - 
someone slumped against a wall. It's a MAN in a nice suit, clearly not from Dayton. 
His clock is flashing red: 00:00:45. Forty-five seconds.

Kai approaches cautiously. The man looks up - he's been beaten. His face is bloody. 
But his eyes are calm, almost peaceful.

MAN: You... you're from here.

KAI: Yeah. Who did this to you?

MAN: Time-keepers. I had... something they wanted. (coughs) Listen. I don't have 
long. Neither do you, in the grand scheme.

KAI: I've got twenty hours. That's more than you.

MAN: (smiles) Twenty hours. You think that's living? That's surviving. There's a 
difference.

The man grabs Kai's arm. Kai tenses - is this a clearing? But the man transfers 
time TO him. The numbers on Kai's forearm jump: 20:16:33 → 100:16:33 → 500:16:33 
→ 1000:16:33... The transfer stops.

Kai stares at his arm in shock. He has over 1000 hours. Over 41 days. The most 
time he's ever had in his life.

KAI: What... why?

MAN: Because you're from here. And you'll know what to do with it. (weakly) 
There's... a file. In my jacket. Left pocket. Take it. Don't let them find it.

The man's clock hits 00:00:00. His eyes go blank. He slides down the wall. Dead.

Kai stands in the alley, breathing hard, staring at his forearm. 1000:16:33. 
He reaches into the man's jacket and pulls out a small data chip. He pockets it 
and runs.

SCENE 6 - INT. KAI'S APARTMENT - NIGHT

Kai barricades his door. He stares at the data chip. It's small, black, 
unmarked. He doesn't have a reader - those cost months of time.

He paces. He looks at his clock: 998:22:17. He's already spent some time thinking. 
Even with a thousand hours, time passes. The realization hits him differently now - 
he has more time, but it's still finite. Still counting down.

He looks at his mother's photo.

KAI: (quietly) I wish you could see this.

He hides the chip inside a crack in the wall behind the photo.

SCENE 7 - INT. MARSHALL ZONE TIME-KEEPER HEADQUARTERS - DAY

Clean, modern, cold. A contrast to Dayton. Screens show zone boundaries, time 
flow data, and flagged anomalies.

SABLE CROSS stands before a HOLOGRAPHIC DISPLAY showing a map of Dayton. A red 
dot blinks - an anomaly.

TECH: Captain Cross, we've got a flag. Unusual time transfer in Dayton. 
Approximately 100 years moved in a single contact.

SABLE: A hundred years? That's not a transfer, that's a redistribution.

TECH: The source timed out immediately after. The recipient... unknown. The 
transfer wasn't logged through any official channel.

SABLE: So someone gave away a century and died for it. (pause) Who was the source?

TECH: Working on identification. But Captain... there's something else. The 
transfer signature doesn't match standard protocols. It's like... it was 
deliberately untraceable.

Sable studies the map. The red dot pulses in Dayton, the poorest zone.

SABLE: Someone wanted this to be found. Or didn't care if it was. Either way, 
a hundred years in Dayton is a bomb. Find the recipient.

SCENE 8 - EXT. THE FRINGE - DAY

The Fringe. Outside the zone system. Makeshift buildings, market stalls, a 
lawless energy. People trade time openly, no regulations, no time-keepers.

ORION VEX sits at an outdoor cafe, drinking coffee that costs 5 minutes. He 
wears a mix of old and new clothes - a vintage leather jacket over a modern 
shirt. His silver hair catches the light.

A YOUNG RUNNER approaches him, out of breath.

RUNNER: Vex. You hear what happened in Dayton?

ORION: I hear everything, eventually. That's the benefit of living three 
centuries. (sips coffee) What specifically?

RUNNER: Someone gave away a hundred years. To a nobody. A factory worker.

Orion's cup pauses halfway to his mouth. His eyes sharpen.

ORION: A hundred years. In Dayton. (sets cup down) That's not charity. That's 
a message. Who was the giver?

RUNNER: Nobody knows. Time-keepers are all over Dayton looking for the receiver.

ORION: Of course they are. A hundred years in the hands of someone who's never 
had more than a day... that's either the most generous act I've seen in a 
century, or the most dangerous. (pause) Find out who died. Not who received - 
who gave. The dead man's identity is the key.

RUNNER: And if the time-keepers find the receiver first?

ORION: Then we have a very short window to intervene. Go.

The runner leaves. Orion looks at his own clock: 3,412:07:22. Over 142 days. 
He's had more. He's had less. He's had millennia and given it away.

ORION: (to himself) A hundred years. Someone's finally making a move.

SCENE 9 - INT. DAYTON PROCESSING FACTORY - DAY

Kai at work, but distracted. He keeps glancing at his clock: 995:44:12. His 
output is slow. The supervisor notices.

SUPERVISOR: Morrow! You're behind again. That's 30 minutes.

KAI: (without thinking) Dock me. I've got time.

The words slip out. The supervisor stares. Other workers look up. In Dayton, 
nobody says "I've got time." It's like saying "I've got money" in a room full 
of starving people.

SUPERVISOR: (suspicious) You've got time?

KAI: I meant... I'll pick it up. Sorry.

The supervisor moves on, but he's watching Kai now. Kai works, heart pounding. 
He's already made a mistake. Having time changes how you act, and people notice.

SCENE 10 - EXT. DAYTON STREETS - EVENING

Kai walks home, more aware of his surroundings than usual. He notices a 
TIME-KEEPER patrolling - not the regular one. This one's from Marshall, 
better uniform, sharper eyes.

Kai changes his route. He walks past the time beggar from Scene 2. The man's 
clock reads 00:01:33. Kai pauses. He has 992 hours. He could give this man 
a day, a week, a month, and never miss it.

He reaches out and grips the man's arm. Time transfers. The beggar's clock 
jumps from 00:01:33 to 168:01:33. A week. The man stares at his arm, then at 
Kai, tears forming.

BEGGAR: Why?

KAI: Because I can. Today.

Kai walks away. He doesn't look back. But across the street, a WOMAN watches 
him. She speaks into a small device.

WOMAN: (quietly) I've got him. Dayton worker, gave away a week to a beggar. 
He's got more than that. A lot more.

SCENE 11 - INT. KAI'S APARTMENT - NIGHT

Kai sits on his mattress, staring at the data chip hidden behind the photo. 
He's been thinking all day. He needs a reader. He needs to know what's on that 
chip. But readers are in Marshall Zone or above, and crossing to Marshall costs 
two months of time.

He has the time now. But the crossing would flag him - a Dayton worker with 
months of time crossing zones? Time-keepers would stop him in minutes.

A knock at the door. Kai tenses, grabs a pipe from under his mattress.

KAI: Who?

VOICE (muffled): Toby. From the line.

Kai opens the door cautiously. TOBY enters, looking nervous.

TOBY: Something's going around. People on the line are talking.

KAI: About what?

TOBY: About you. Supervisor told some people you said "I've got time." And 
someone saw you give a week to the beggar on Fifth Street. (pause) People are 
talking, Kai. Some are happy for you. Some are... not.

KAI: Not?

TOBY: Jealous. Scared. Or planning. You know how it is. When someone has 
something, everyone else wants to know how they got it. And if the time-keepers 
hear...

KAI: I know.

TOBY: Be careful. Whatever you've got, whatever happened... be careful. This 
is Dayton. Generosity gets you killed here.

Toby leaves. Kai locks the door. His clock reads 989:33:44.

SCENE 12 - INT. MARSHALL ZONE TIME-KEEPER HQ - NIGHT

Sable at her desk. Screens show data. The TECH from earlier approaches.

TECH: Captain. We identified the source. The man who gave away the century.

SABLE: Who was he?

TECH: Name was Marcus Cole. (pulls up file) He was... interesting. Former Time 
Authority analyst. Worked in the Algorithm Division. Disappeared six months ago. 
Was presumed to have crossed to Greenwich.

SABLE: An analyst with a century of time giving it away in Dayton. That's not 
random. (reads file) Algorithm Division... what did he work on?

TECH: That's classified. Level 7 clearance. Above your grade, Captain.

Sable stares at the tech.

SABLE: A man from the Algorithm Division gave away a hundred years to a stranger 
in Dayton and then died. And the algorithm he worked on is classified. (stands) 
Get me Level 7 access. Now.

TECH: I can't just—

SABLE: Then get me someone who can. A dead analyst's secrets just walked into 
Dayton in someone's pocket. Every second we wait, that data gets closer to 
people who'll use it.

SCENE 13 - EXT. DAYTON ROOFTOP - NIGHT

Kai sits on the roof of his building, looking out over Dayton. The zone is a 
patchwork of dim lights, smoke, and desperation. In the far distance, the bright 
towers of Greenwich glow like a separate world.

He looks at his clock: 987:22:08. He has time. For the first time in his life, 
he has time. And he has a data chip he can't read, a dead man's secret he can't 
decode, and time-keepers looking for him.

He holds up the chip to the dim light. Small, black, silent.

KAI: (to himself) What did you give me, Marcus Cole?

The camera pulls back, showing Kai alone on the rooftop, the vast inequality of 
the zones spread out before him. Greenwich glows. Dayton flickers. And somewhere 
in between, Sable Cross is getting Level 7 clearance.

SCENE 14 - INT. ORION'S SHOP - THE FRINGE - NIGHT

Orion's shop is a cluttered space filled with old technology, time capsules, 
and curiosities from different decades. A young WOMAN sits across from him.

ORION: So you want to know about Marcus Cole.

WOMAN: You knew him?

ORION: I know everyone who matters, eventually. Marcus was... idealistic. 
Dangerously so. He worked in the Algorithm Division - the part of the Time 
Authority that manages the flow of time between zones. The economic engine.

WOMAN: What did he find?

ORION: (pause) You know what a 'time sink' is?

WOMAN: Like... a leak in the system?

ORION: Exactly. Marcus found a time sink. Not a natural one - a deliberate one. 
Someone, or some group within the Authority, has been siphoning time from the 
lower zones. Not stealing it - destroying it. Reducing the total time in 
circulation in Dayton, Paco, and Marshall. Making people time out faster.

WOMAN: Why?

ORION: Inflation control. If too much time circulates in the lower zones, the 
economy destabilizes. The rich stay rich by keeping the poor... poor. And dead. 
(pause) Marcus couldn't live with it. So he took the evidence and gave it to 
someone who could use it. Someone from Dayton.

WOMAN: The factory worker.

ORION: The factory worker. And now the question is: will that worker use the 
data, or will the Time Authority find him first? (looks at clock) It's a race. 
And I've seen this race before. Fifty years ago. Will Salas ran it.

WOMAN: What happened to Will Salas?

ORION: (enigmatic smile) That depends on who you ask. Good night, Lena.

SCENE 15 - INT. KAI'S APARTMENT - LATE NIGHT

Kai can't sleep. He looks at the chip again. He makes a decision. He needs to 
get to The Fringe. No zone boundaries, no time-keepers, and someone there can 
read this chip.

He puts on his jacket, takes the chip from its hiding place, and heads for the 
door. His clock: 985:44:21.

He opens the door. Two TIME-KEEPERS stand in the hallway.

TIME-KEEPER 1: Kai Morrow?

KAI: (freezes) Yeah.

TIME-KEEPER 1: You need to come with us. Questions about an unusual time 
transfer.

Kai looks at their uniforms. Marshall Zone time-keepers. Not local. They're 
here for him.

KAI: I haven't done anything wrong.

TIME-KEEPER 2: Nobody said you did. We just need to talk. (holds out arm) 
Transfer check. Standard procedure.

Kai knows what a transfer check means - they'll read his time log and see the 
century transfer. He'll be detained. The chip will be found.

KAI: (quietly) How about we talk at the station? I'll walk with you.

TIME-KEEPER 1: That's not how this works.

Kai looks at the time-keeper's outstretched arm. He looks at his own clock. 
985:44:08. He has time. He has enough time to run.

He runs.

SCENE 16 - EXT. DAYTON STREETS - NIGHT

Kai bursts out of his building, sprinting down the street. The time-keepers 
shout and chase. Their radios crackle.

Kai knows Dayton's alleys better than anyone - he's been running these streets 
since he was a kid. He dodges through narrow passages, over fences, under 
pipes. The time-keepers are fit but they don't know the territory.

He loses them in the industrial district. He leans against a wall, breathing 
hard, his clock ticking: 984:12:33. Running costs time. Everything costs time.

He looks toward the edge of Dayton. Beyond it, The Fringe. No rules. No 
time-keepers. And someone who can read a data chip.

He starts walking. The camera follows him from behind as he heads toward the 
zone boundary, the dim lights of The Fringe visible in the distance.

His clock ticks. The screen fades to black.

TEXT ON SCREEN: "In this world, time is money. But what happens when someone 
steals the clock?"

END OF EPISODE 1

NEXT TIME ON IN TIME: Kai enters The Fringe and meets Orion Vex. Sable 
investigates the Algorithm Division. And Mira Santos discovers something in 
the time-transfer code that changes everything.
"""

def get_series_bible():
    return SERIES_BIBLE

def get_episode_1_script():
    return EPISODE_1_SCRIPT

def get_season_arc(season_num):
    return SERIES_BIBLE.get("season_arcs", {}).get(str(season_num), {})

if __name__ == "__main__":
    bible = get_series_bible()
    print(f"Series: {bible['title']}")
    print(f"Concept: {bible['concept'][:100]}...")
    print(f"Seasons: {bible['seasons_planned']}, Episodes per season: {bible['episodes_per_season']}")
    print(f"Characters: {len(bible['characters'])}")
    for cid, char in bible['characters'].items():
        print(f"  - {char['name']}: {char['description'][:60]}...")
    
    ep1 = get_episode_1_script()
    word_count = len(ep1.split())
    print(f"\nEpisode 1: {word_count} words")
    print(f"Season arcs: {len(bible['season_arcs'])}")
