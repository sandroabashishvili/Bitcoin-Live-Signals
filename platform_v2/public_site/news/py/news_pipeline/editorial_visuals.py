"""Original, deterministic article illustrations, never charts of actual prices."""
from hashlib import sha256
import re
from .source_policy import SOURCE_POLICIES

# Specific topics precede the broad market fallback. Classification is descriptive,
# not a prediction of an article's market impact.
TOPICS = (
    ('security', 'SECURITY & TRUST', r'\bcyber\w*|\bmalware\b|\bvulnerabilit\w*|\bhack\w*|\bexploit\w*|\btheft\b|\bstolen\b|\bsecurity\b|\bfraud\b'),
    ('regulation', 'POLICY & REGULATION', r'\bsec\b|\bcftc\b|\bfca\b|\bofac\b|\bsanctions?\b|\bauthorisation\b|\bregulat\w*|\blegislat\w*|\bcourt\b|\blawsuit\b'),
    ('funds', 'FUNDS & INSTITUTIONS', r'\betfs?\b|\btreasur\w*|\bfunds?\b|\binstitution\w*|\bgrayscale\b|\bblackrock\b|\bfidelity\b'),
    ('payments', 'PAYMENTS & STABLECOINS', r'\bstablecoins?\b|\bpayments?\b|\busdt\b|\busdc\b|\bremittances?\b'),
    ('exchange', 'EXCHANGES & TRADING', r'\bexchange\w*|\bbinance\b|\bcoinbase\b|\bkraken\b|\bderivatives?\b|\bfutures\b|\blisting\b'),
    ('technology', 'BLOCKCHAIN & NETWORKS', r'\bblockchains?\b|\bcleanspark\b|\bprotocol\b|\bupgrade\w*|\bmining\b|\bhashrate\b|\boptech\b|\bnetwork\b|\bdefi\b'),
    ('monetary', 'MACRO & MONETARY POLICY', r'\binflation\b|\binterest rates?\b|\bfomc\b|\bgdp\b|\bcentral bank\b|\becb\b|\bfederal reserve\b'),
)

DRAWINGS = {
    'security': '<path d="M320 40L400 72V123Q400 170 320 202Q240 170 240 123V72Z"/><rect x="285" y="104" width="70" height="52" rx="9"/><path d="M300 104V89a20 20 0 0 1 40 0v15M320 123v15"/>',
    'regulation': '<path d="M320 42V181M225 78H415M245 78L210 140H280ZM395 78L360 140H430ZM273 192H367"/><circle cx="320" cy="62" r="12"/>',
    'funds': '<rect x="235" y="77" width="170" height="112" rx="14"/><path d="M283 77V50H357V77M235 114H405M305 110V130H335V110"/><circle cx="442" cy="157" r="30"/><path d="M442 140V174M430 157H454"/>',
    'payments': '<rect x="190" y="67" width="137" height="90" rx="14"/><path d="M190 91H327M352 92H442L425 75M442 92L425 109M440 166H350L367 149M350 166L367 183"/><circle cx="382" cy="128" r="19"/>',
    'exchange': '<rect x="189" y="53" width="94" height="139" rx="14"/><rect x="357" y="53" width="94" height="139" rx="14"/><path d="M219 90H253M219 116H253M219 142H245M384 90H425M384 116H419M384 142H425M288 100H348L333 85M348 100L333 115M348 152H288L303 137M288 152L303 167"/>',
    'technology': '<path d="M216 85L320 52L424 85V155L320 190L216 155ZM216 85L320 122L424 85M320 122V190M268 69L373 105M268 173V103L373 69"/><circle cx="172" cy="120" r="12"/><circle cx="468" cy="120" r="12"/><path d="M184 120H216M424 120H456"/>',
    'monetary': '<path d="M205 87L320 40L435 87ZM210 177H430M195 192H445M239 104V162M293 104V162M347 104V162M401 104V162"/>',
    'markets': '<circle cx="320" cy="120" r="78"/><ellipse cx="320" cy="120" rx="37" ry="78"/><path d="M242 120H398M254 82H386M254 158H386"/><path d="M207 62L180 95L212 95M433 177L460 144L428 144"/>',
}
PALETTES = {
    'security': ('#ffa6b9', '#301c30'), 'regulation': ('#c3b2ff', '#251d43'),
    'funds': ('#a4baff', '#182b4a'), 'payments': ('#88ebbb', '#12352e'),
    'exchange': ('#78def7', '#123042'), 'technology': ('#ffcc83', '#342918'),
    'monetary': ('#91d8d2', '#163538'), 'markets': ('#f4ab7b', '#3a231f'),
}


def classify_topic(source: str, title: str) -> tuple[str, str]:
    for topic, label, pattern in TOPICS:
        if re.search(pattern, title, re.I):
            return topic, label
    policy = SOURCE_POLICIES.get(source)
    fallback = {'bitcoin': 'technology', 'regulation': 'regulation', 'monetary': 'monetary'}.get(policy.topic if policy else '', 'markets')
    labels = {topic: label for topic, label, _ in TOPICS}
    return fallback, labels.get(fallback, 'CRYPTO MARKETS')


def render_editorial_visual(source: str, *, title: str = '', identity: str = '') -> str:
    topic, label = classify_topic(source, title)
    variant = sha256((identity or title or source).encode()).digest()[0] % 3
    color, background = PALETTES[topic]
    decorations = (
        '<circle cx="80" cy="30" r="100"/><circle cx="580" cy="215" r="105"/>',
        '<path d="M0 0L180 240M65 0L245 240M410 0L590 240M475 0L655 240"/>',
        '<rect x="38" y="55" width="125" height="125" rx="32"/><circle cx="548" cy="108" r="65"/>',
    )[variant]
    return f'''<div class="news-editorial news-editorial-{topic}" style="color:{color};background:{background}">
<svg viewBox="0 0 640 240" aria-hidden="true" focusable="false"><g fill="none" stroke="currentColor" stroke-width="2" opacity=".16">{decorations}</g><g fill="none" stroke="currentColor" stroke-width="3.5" stroke-linejoin="round" stroke-linecap="round">{DRAWINGS[topic]}</g></svg>
<div class="news-editorial-caption"><span>{label}</span><span>ILLUSTRATION</span></div></div>'''
