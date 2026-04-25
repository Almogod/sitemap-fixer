# src/content/stopwords.py
"""
Comprehensive English stopwords list — single source of truth for all
keyword extraction, LSI analysis, and content quality modules.

Categories covered:
  - Articles & determiners
  - Prepositions & postpositions
  - Pronouns (personal, possessive, demonstrative, relative, indefinite)
  - Conjunctions (coordinating, subordinating, correlative)
  - Auxiliary & modal verbs
  - Common adverbs
  - Common adjectives (non-semantic)
  - Web & URL noise
  - SEO / HTML noise
  - Generic filler words
"""

STOPWORDS: frozenset = frozenset({
    # ── Articles & determiners ────────────────────────────────────────
    "a", "an", "the", "this", "that", "these", "those",
    "some", "any", "each", "every", "all", "both", "few",
    "many", "much", "several", "enough", "no", "none",

    # ── Prepositions ──────────────────────────────────────────────────
    "about", "above", "across", "after", "against", "along", "among",
    "around", "at", "before", "behind", "below", "beneath", "beside",
    "besides", "between", "beyond", "by", "concerning", "despite",
    "down", "during", "except", "for", "from", "in", "inside", "into",
    "like", "near", "of", "off", "on", "onto", "out", "outside",
    "over", "past", "per", "regarding", "since", "through",
    "throughout", "till", "to", "toward", "towards", "under",
    "underneath", "until", "unto", "up", "upon", "via", "with",
    "within", "without",

    # ── Pronouns ──────────────────────────────────────────────────────
    "i", "me", "my", "mine", "myself",
    "you", "your", "yours", "yourself", "yourselves",
    "he", "him", "his", "himself",
    "she", "her", "hers", "herself",
    "it", "its", "itself",
    "we", "us", "our", "ours", "ourselves",
    "they", "them", "their", "theirs", "themselves",
    "what", "which", "who", "whom", "whose",
    "whoever", "whatever", "whichever",
    "something", "anything", "everything", "nothing",
    "someone", "anyone", "everyone", "nobody",
    "somewhere", "anywhere", "everywhere", "nowhere",
    "one", "ones", "other", "others", "another",

    # ── Conjunctions ──────────────────────────────────────────────────
    "and", "but", "or", "nor", "for", "yet", "so",
    "because", "although", "though", "even", "if", "unless",
    "while", "whereas", "whether", "once", "since", "than",
    "that", "when", "whenever", "where", "wherever", "after",
    "before", "until", "as", "either", "neither", "not", "only",
    "both",

    # ── Auxiliary & modal verbs ───────────────────────────────────────
    "am", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "having",
    "do", "does", "did", "doing", "done",
    "will", "would", "shall", "should",
    "can", "could", "may", "might", "must",
    "need", "dare", "ought",

    # ── Common verb forms (non-semantic) ──────────────────────────────
    "get", "gets", "got", "getting", "gotten",
    "make", "makes", "made", "making",
    "go", "goes", "went", "going", "gone",
    "come", "comes", "came", "coming",
    "take", "takes", "took", "taking", "taken",
    "give", "gives", "gave", "giving", "given",
    "say", "says", "said", "saying",
    "see", "sees", "saw", "seeing", "seen",
    "know", "knows", "knew", "knowing", "known",
    "think", "thinks", "thought", "thinking",
    "want", "wants", "wanted", "wanting",
    "use", "uses", "used", "using",
    "find", "finds", "found", "finding",
    "put", "puts", "putting",
    "tell", "tells", "told", "telling",
    "ask", "asks", "asked", "asking",
    "seem", "seems", "seemed", "seeming",
    "feel", "feels", "felt", "feeling",
    "try", "tries", "tried", "trying",
    "leave", "leaves", "left", "leaving",
    "call", "calls", "called", "calling",
    "keep", "keeps", "kept", "keeping",
    "let", "lets", "letting",
    "begin", "begins", "began", "beginning", "begun",
    "show", "shows", "showed", "showing", "shown",
    "hear", "hears", "heard", "hearing",
    "play", "plays", "played", "playing",
    "run", "runs", "ran", "running",
    "move", "moves", "moved", "moving",
    "live", "lives", "lived", "living",
    "believe", "believes", "believed", "believing",
    "bring", "brings", "brought", "bringing",
    "happen", "happens", "happened", "happening",
    "set", "sets", "setting",
    "sit", "sits", "sat", "sitting",
    "stand", "stands", "stood", "standing",
    "turn", "turns", "turned", "turning",
    "start", "starts", "started", "starting",
    "hold", "holds", "held", "holding",
    "write", "writes", "wrote", "writing", "written",
    "provide", "provides", "provided", "providing",
    "read", "reads", "reading",
    "allow", "allows", "allowed", "allowing",
    "add", "adds", "added", "adding",
    "spend", "spends", "spent", "spending",
    "grow", "grows", "grew", "growing", "grown",
    "open", "opens", "opened", "opening",
    "walk", "walks", "walked", "walking",
    "offer", "offers", "offered", "offering",
    "remember", "remembers", "remembered", "remembering",
    "consider", "considers", "considered", "considering",
    "appear", "appears", "appeared", "appearing",
    "buy", "buys", "bought", "buying",
    "serve", "serves", "served", "serving",
    "die", "dies", "died", "dying",
    "send", "sends", "sent", "sending",
    "build", "builds", "built", "building",
    "stay", "stays", "stayed", "staying",
    "fall", "falls", "fell", "falling", "fallen",
    "cut", "cuts", "cutting",
    "reach", "reaches", "reached", "reaching",
    "remain", "remains", "remained", "remaining",
    "suggest", "suggests", "suggested", "suggesting",
    "raise", "raises", "raised", "raising",
    "pass", "passes", "passed", "passing",
    "sell", "sells", "sold", "selling",
    "require", "requires", "required", "requiring",
    "report", "reports", "reported", "reporting",
    "decide", "decides", "decided", "deciding",
    "pull", "pulls", "pulled", "pulling",
    "develop", "develops", "developed", "developing",
    "look", "looks", "looked", "looking",
    "carry", "carries", "carried", "carrying",
    "lose", "loses", "lost", "losing",
    "pay", "pays", "paid", "paying",
    "meet", "meets", "met", "meeting",
    "include", "includes", "included", "including",
    "continue", "continues", "continued", "continuing",
    "learn", "learns", "learned", "learning",
    "change", "changes", "changed", "changing",
    "lead", "leads", "led", "leading",
    "understand", "understands", "understood", "understanding",
    "watch", "watches", "watched", "watching",
    "follow", "follows", "followed", "following",
    "stop", "stops", "stopped", "stopping",
    "create", "creates", "created", "creating",
    "speak", "speaks", "spoke", "speaking", "spoken",
    "apply", "applies", "applied", "applying",
    "wait", "waits", "waited", "waiting",
    "save", "saves", "saved", "saving",
    "cause", "causes", "caused", "causing",
    "drive", "drives", "drove", "driving",
    "place", "places", "placed", "placing",

    # ── Common adverbs ────────────────────────────────────────────────
    "also", "just", "very", "often", "however", "too", "usually",
    "really", "already", "always", "never", "sometimes", "still",
    "now", "then", "here", "there", "where", "how", "why",
    "again", "further", "once", "soon", "well", "almost",
    "enough", "quite", "rather", "somewhat", "perhaps", "maybe",
    "actually", "certainly", "clearly", "probably", "simply",
    "therefore", "thus", "hence", "accordingly", "consequently",
    "instead", "otherwise", "nevertheless", "nonetheless",
    "meanwhile", "moreover", "furthermore", "indeed", "finally",
    "specifically", "especially", "particularly", "generally",
    "basically", "essentially", "obviously", "apparently",
    "recently", "currently", "especially", "definitely",
    "merely", "mostly", "partly", "entirely", "completely",
    "fairly", "slightly", "roughly", "largely",

    # ── Common adjectives (non-semantic) ──────────────────────────────
    "good", "great", "new", "old", "big", "small", "large",
    "long", "short", "high", "low", "first", "last", "next",
    "own", "same", "different", "able", "possible", "likely",
    "important", "available", "sure", "free", "full", "real",
    "right", "left", "best", "better", "worse", "worst",
    "certain", "true", "false", "whole", "main", "major",
    "general", "common", "public", "private", "simple",

    # ── Numbers & ordinals ────────────────────────────────────────────
    "zero", "one", "two", "three", "four", "five", "six",
    "seven", "eight", "nine", "ten", "hundred", "thousand",
    "million", "billion",

    # ── Question words & relative ─────────────────────────────────────
    "how", "why", "what", "when", "where", "which", "who",
    "whom", "whose",

    # ── Contractions (as they appear after tokenization) ──────────────
    "dont", "doesnt", "didnt", "cant", "couldnt", "shouldnt",
    "wouldnt", "wont", "isnt", "arent", "wasnt", "werent",
    "hasnt", "havent", "hadnt", "mustnt",
    "ive", "youve", "weve", "theyve",
    "ill", "youll", "hell", "shell", "well", "theyll",
    "im", "youre", "hes", "shes", "its", "were", "theyre",
    "hed", "shed", "wed", "theyd",
    "thats", "whats", "heres", "theres", "whos",

    # ── Web & URL noise ───────────────────────────────────────────────
    "http", "https", "www", "com", "org", "net", "edu", "gov",
    "html", "htm", "php", "asp", "aspx", "jsp",
    "png", "jpg", "jpeg", "gif",
    "svg", "ico", "webp", "mp4", "mp3", "wav",
    "href", "src", "alt",
    "click", "here", "more", "view",
    "share", "tweet", "reply",
    "signup", "register", "subscribe", "submit",
    "menu", "nav", "navigation", "sidebar",
    "header", "footer", "cookie", "cookies", "privacy",
    "terms", "disclaimer", "copyright",

    # ── HTML noise (not semantic) ─────────────────────────────────────
    "class", "style", "div", "span",
    "aside", "body", "head",
    "script", "noscript", "iframe", "embed", "object",

    # ── Generic filler & transition words ─────────────────────────────
    "thing", "things", "stuff", "way", "ways", "lot", "lots",
    "kind", "kinds", "sort", "sorts",
    "piece", "pieces", "bit", "bits",
    "point", "points", "fact", "facts", "case", "cases",
    "time", "times", "day", "days", "year", "years",
    "example", "examples", "instance", "instances",
    "reason", "reasons", "number", "numbers",
    "hand", "hands", "end", "ends",
    "side", "sides", "line", "lines",
    "word", "words",
    "note", "notes",
    "figure",
    "according", "based", "related", "various",
    "today", "tomorrow", "yesterday",
    "detail", "details",
    "person", "man", "woman", "men", "women",
    "child", "children",
    "order", "world", "country", "countries",
    "house", "family",
    "eye", "eyes", "face",
    "back", "city", "room",
    "member", "members",
    "period",
    "percent", "month", "months", "week", "weeks",
    "names",

    # ── Misc utility words ────────────────────────────────────────────
    "etc", "eg", "ie", "vs", "via",
    "please", "thank", "thanks", "sorry",
    "yes", "yeah", "yep", "no", "nope", "okay", "ok",
    "hello", "hi", "hey", "dear", "sir", "madam",
})


# ── Convenience helpers ───────────────────────────────────────────────

def is_stopword(word: str) -> bool:
    """Check if a word is a stopword (case-insensitive)."""
    return word.lower() in STOPWORDS


def filter_stopwords(tokens: list[str]) -> list[str]:
    """Remove stopwords from a list of tokens."""
    return [t for t in tokens if t.lower() not in STOPWORDS]


def filter_stopwords_min_length(tokens: list[str], min_len: int = 3) -> list[str]:
    """Remove stopwords and tokens shorter than min_len."""
    return [t for t in tokens if len(t) >= min_len and t.lower() not in STOPWORDS]
