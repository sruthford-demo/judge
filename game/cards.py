"""Card data for Judge: prompt ("black") cards and response ("white") cards."""

from dataclasses import dataclass


@dataclass(frozen=True)
class PromptCard:
    id: str
    text: str
    emoji: str = "❓"


@dataclass(frozen=True)
class ResponseCard:
    id: str
    text: str
    emoji: str


PROMPT_CARDS: tuple[PromptCard, ...] = (
    PromptCard("p01", "The real reason I was late to the wedding: ___.", "💒"),
    PromptCard("p02", "Grandma's secret family recipe turned out to be ___.", "🍲"),
    PromptCard("p03", "TSA pulled me aside because of my ___.", "🛂"),
    PromptCard("p04", "My dating app bio just says '___' and I still get matches.", "📱"),
    PromptCard("p05", "The new-employee orientation video opened with a slide about ___.", "📽️"),
    PromptCard("p06", "I got banned from the community pool because of my ___.", "🏊"),
    PromptCard("p07", "The home inspector's report flagged exactly one thing: ___.", "🏠"),
    PromptCard("p08", "My eulogy will probably mention my ___.", "🕊️"),
    PromptCard("p09", "The wellness retreat's icebreaker was 'show the group your ___.'", "🧘"),
    PromptCard("p10", "Right before the job interview, I forgot to deal with my ___.", "💼"),
    PromptCard("p11", "The class photo had to be retaken because of someone's ___.", "📸"),
    PromptCard("p12", "My dating profile's 'red flags' section just lists my ___.", "🚩"),
    PromptCard("p13", "Instead of flowers, I brought my mother-in-law ___.", "💐"),
    PromptCard("p14", "The company all-hands ended awkwardly when HR mentioned my ___.", "🏢"),
    PromptCard("p15", "The airport security scanner lit up because of my ___.", "🛃"),
    PromptCard("p16", "My yearbook superlative was 'Most Likely to Have ___.'", "📖"),
    PromptCard("p17", "The bridezilla meltdown started the moment she saw my ___.", "👰"),
    PromptCard("p18", "The new roommate's first question was about my ___.", "🔑"),
)

RESPONSE_CARDS: tuple[ResponseCard, ...] = (
    ResponseCard("r01", "Camel toe", "🍑"),
    ResponseCard("r02", "Back hair", "🦍"),
    ResponseCard("r03", "An unsightly yard", "🌿"),
    ResponseCard("r04", "A banana hammock", "🍌"),
    ResponseCard("r05", "A unibrow", "🐛"),
    ResponseCard("r06", "Moldy cheese", "🧀"),
    ResponseCard("r07", "A front-yard toilet planter", "🚽"),
    ResponseCard("r08", "A fanny pack full of expired coupons", "👝"),
    ResponseCard("r09", "Chronic dandruff", "🌨️"),
    ResponseCard("r10", "A sweat stain shaped like Florida", "🗺️"),
    ResponseCard("r11", "An overflowing drawer of participation trophies", "🏆"),
    ResponseCard("r12", "A jar of toenail clippings", "💅"),
    ResponseCard("r13", "Crocs worn with socks", "🧦"),
    ResponseCard("r14", "A suspicious rash", "🔴"),
    ResponseCard("r15", "Nostril hair you could braid", "🧵"),
    ResponseCard("r16", "A garage full of unopened blenders", "📦"),
    ResponseCard("r17", "An emotional-support fanny pack", "🎒"),
    ResponseCard("r18", "A neck beard", "🧔"),
    ResponseCard("r19", "A 'World's Okayest Dad' mug collection", "☕"),
    ResponseCard("r20", "Bunions the size of golf balls", "⛳"),
    ResponseCard("r21", "A drawer of tangled charging cables", "🔌"),
    ResponseCard("r22", "A lazy eye that wanders mid-conversation", "👁️"),
    ResponseCard("r23", "Love handles spilling over cutoff jorts", "👖"),
    ResponseCard("r24", "A mullet grown out of pure spite", "💇"),
    ResponseCard("r25", "Chronic flatulence at the worst moments", "💨"),
    ResponseCard("r26", "A yard-gnome collection topping 40 gnomes", "🧙"),
    ResponseCard("r27", "Crusty flip-flops from 2009", "🩴"),
    ResponseCard("r28", "A neck tattoo of an ex's name", "🖋️"),
    ResponseCard("r29", "An expired gym membership you still brag about", "🏋️"),
    ResponseCard("r30", "A fungal toenail you refuse to treat", "🦶"),
    ResponseCard("r31", "A minivan with a 'Baby on Board' sign and no baby", "🚐"),
    ResponseCard("r32", "A sunburn shaped exactly like a tank top", "🌞"),
    ResponseCard("r33", "Gap in teeth", "🦷"),
    ResponseCard("r34", "Loonie Tunes themed clothing on an adult", "🐰"),
    ResponseCard("r35", "Camo", "🌲"),
    ResponseCard("r36", "White Trash Wedding pic", "💍"),
    ResponseCard("r37", "Posing with a snake", "🐍"),
    ResponseCard("r38", "Hairy armpit", "💪"),
    ResponseCard("r39", "Dog poop on carpet", "💩"),
    ResponseCard("r40", "Hairless cat", "🐈"),
    ResponseCard("r41", "Kid on a backpack leash", "🎒"),
    ResponseCard("r42", "Crying child", "😭"),
    ResponseCard("r43", "Trump", "🧑‍💼"),
    ResponseCard("r44", "Obama", "🎓"),
    ResponseCard("r45", "Hangnail", "💅"),
    ResponseCard("r46", "Cabinet door ajar", "🚪"),
    ResponseCard("r47", "Farmers tan", "☀️"),
    ResponseCard("r48", "Ankle tan", "🦵"),
    ResponseCard("r49", "Lazy eye", "👁️"),
    ResponseCard("r50", "Pimple", "🔴"),
    ResponseCard("r51", "Karen hair", "💇‍♀️"),
    ResponseCard("r52", "Rattail", "🐀"),
    ResponseCard("r53", "Wart", "🟤"),
    ResponseCard("r54", "Incorrect grammar", "📝"),
    ResponseCard("r55", "Parking over the line", "🅿️"),
    ResponseCard("r56", "Bruised banana", "🍌"),
    ResponseCard("r57", "Fruit fly", "🪰"),
    ResponseCard("r58", "Tramp stamp", "🖊️"),
    ResponseCard("r59", "Mullet", "💇"),
    ResponseCard("r60", "Vomit", "🤮"),
    ResponseCard("r61", "Bed bug", "🛏️"),
    ResponseCard("r62", "Mosquitos", "🦟"),
    ResponseCard("r63", "Mosquito bite", "🩹"),
    ResponseCard("r64", "Rash", "🔴"),
    ResponseCard("r65", "To do list", "✅"),
    ResponseCard("r66", "Midget", "📏"),
    ResponseCard("r67", "Handicapped parking sign", "♿"),
    ResponseCard("r68", "Rush hour traffic", "🚗"),
    ResponseCard("r69", "Bleating goat", "🐐"),
    ResponseCard("r70", "Cop lights", "🚨"),
    ResponseCard("r71", "Sliver", "🪵"),
    ResponseCard("r72", "Goosebumps", "🐔"),
    ResponseCard("r73", "Spider", "🕷️"),
    ResponseCard("r74", "Snake", "🐍"),
)

PROMPT_BY_ID: dict[str, PromptCard] = {c.id: c for c in PROMPT_CARDS}
RESPONSE_BY_ID: dict[str, ResponseCard] = {c.id: c for c in RESPONSE_CARDS}
