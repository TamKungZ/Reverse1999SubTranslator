BASIC = """
a about above after again all also am an and any are as at back be because been before being but by can come could
day did do does don't down each even first for from get give go good had has have he her here him his how i if in into
is it its just know like look make me more most my new no not now of on one only or other our out over people say see
she so some take than that the their them then there these they thing think this those time to two up us use want was
way we well were what when which who will with would year you your always never still much many very too really right
left feel tell ask need try let put keep call work life man woman child world house room door hand eye head face heart
friend love night today tomorrow yesterday maybe please thank thanks sorry yes okay ok sure oh hey hello bye off away
let's i'm i'll i've i'd it's that's there's what's don't doesn't didn't won't can't couldn't wouldn't isn't aren't
wasn't weren't hasn't haven't you're you'll you've we're we'll we've they're they'll they've he's she's who's
told said went came made took saw got gave found knew thought felt left kept began seemed became
three four five six seven eight nine ten hundred thousand little big long great own same another such both every
nothing something anything everything someone anyone everyone nobody where why while though through under until
without within around between against during since upon whether either neither else ever once twice
""".split()

MEDIUM = """
able across act add afraid age ago agree air alone along already although among animal answer appear arrive art bad
bag beautiful become bed begin behind believe best better bird black blood blue body book bring brother build busy
buy care carry case catch cause change check city class clean clear close cold color complete country course cry cut
dark dead dear decide deep different difficult dinner dream drink drive early earth easy eat end enough enter escape
evening exactly expect explain fall family far fast father fear few field fight final find fine finish fire fish
follow food foot forget forgive free fresh front full future game garden gentle girl glad glass gold gone green
ground group grow guess hair half happen happy hard hate hear heavy help hide high hold hope hot hour human hurry
idea important inside invite island job join journey kill kind king knock land large last late laugh lead learn leave
less letter lie light line listen live lonely lose lost loud low luck mad main mean meet memory mind minute miss
mistake money month moon morning mother mountain mouth move music must name near nearly noise notice number ocean
offer often old open order outside pain paper part pass past pay peace perhaps person place plan play pull push quick
quiet rain reach read ready real reason remember rest return rich ride river road rock rule run sad safe save school
sea search second secret seem sell send serious several shall share ship short should show side silent simple sing
sister sit sky sleep slow small smile snow soft soldier sometimes son song soon sound speak special spend stand star
start stay step stone stop story strange street strong sudden sun surprise sweet table talk teach tear terrible test
throw tired together tonight touch town travel tree trouble true trust truth turn understand usual voice wait walk
wall war warm wash watch water wave weather week welcome west whole wide wild win wind window wing winter wish
wonder wood word worry wrong young bright company sail
""".split()

_BASIC = frozenset(BASIC)
_MEDIUM = _BASIC | frozenset(MEDIUM)


def _variants(word):
    yield word
    for suf in ("s", "es", "ed", "d", "ing", "ly", "er", "est"):
        if word.endswith(suf) and len(word) - len(suf) >= 3:
            stem = word[: -len(suf)]
            yield stem
            yield stem + "e"
            if len(stem) > 3 and stem[-1] == stem[-2]:
                yield stem[:-1]
    if word.endswith("ies") and len(word) > 4:
        yield word[:-3] + "y"


def is_common(word, level):
    if level == "off":
        return False
    pool = _MEDIUM if level == "medium" else _BASIC
    word = word.lower()
    return any(v in pool for v in _variants(word))
