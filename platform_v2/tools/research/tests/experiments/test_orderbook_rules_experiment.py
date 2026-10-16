import ast
from types import SimpleNamespace
import pytest
from platform_v2.tools.research.orderbook_rules_experiment import candidate_source, RULES
from platform_v2.tools.research.orderbook_rules_experiment import audit_complete_inputs
from platform_v2.spot.services.signal.long_component_score_service import SpotLongComponentScoreService as Original

from platform_v2.tools.research.tests.paths import PLATFORM_ROOT

SOURCE = PLATFORM_ROOT / 'spot/services/signal/long_component_score_service.py'


def candidate(variant):
    namespace={};exec(compile(candidate_source(SOURCE.read_text(),variant),str(SOURCE),'exec'),namespace)
    return namespace['SpotLongComponentScoreService']


@pytest.mark.parametrize('variant',RULES)
def test_only_shared_orderbook_method_changes(variant):
    trees=[ast.parse(SOURCE.read_text()),ast.parse(candidate_source(SOURCE.read_text(),variant))]
    for tree in trees:
        cls=next(n for n in tree.body if isinstance(n,ast.ClassDef))
        method=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='directional_orderbook_score')
        method.body=[ast.Pass()]
    assert ast.dump(trees[0])==ast.dump(trees[1])


@pytest.mark.parametrize('d,points',[(-.5,0),(0,0),(.01,.75),(.099,.75),(.1,1.5),(.249,1.5),(.25,2.25),(.499,2.25),(.5,2.5),(.99,2.5)])
def test_monotonic_boundaries(d,points):
    book=SimpleNamespace(buyers=1+d,sellers=1-d,dominance_ratio=d,imbalance=d)
    assert candidate('monotonic').long_orderbook_score(book)==points


@pytest.mark.parametrize('variant',RULES)
def test_mirror_and_missing(variant):
    cls=candidate(variant)
    assert cls.long_orderbook_score(None)==cls.short_orderbook_score(None)==0
    for d in (-.9,-.5,-.25,-.1,0,.1,.25,.5,.9):
        book=SimpleNamespace(buyers=1+d,sellers=1-d,dominance_ratio=d,imbalance=d)
        mirror=SimpleNamespace(buyers=1-d,sellers=1+d,dominance_ratio=-d,imbalance=-d)
        assert cls.long_orderbook_score(book)==cls.short_orderbook_score(mirror)


def test_no_imbalance_removes_only_original_confirmation():
    cls=candidate('no_imbalance')
    for d in (-.9,-.5,-.25,0,.04,.05,.1,.25,.5,.9):
        book=SimpleNamespace(buyers=1+d,sellers=1-d,dominance_ratio=d,imbalance=d)
        delta=.25 if .05<=d<.5 else -.25 if d>=.5 else 0
        # Clamp after removing the original confirmation, including negative tails.
        if d<.5:assert cls.long_orderbook_score(book)==pytest.approx(Original.long_orderbook_score(book)-delta)
        assert 0<=cls.long_orderbook_score(book)<=3


def test_disabled_is_diagnostic_zero_only():
    cls=candidate('disabled')
    book=SimpleNamespace(buyers=2,sellers=1,dominance_ratio=1/3,imbalance=1/3)
    assert cls.long_orderbook_score(book)==cls.short_orderbook_score(book)==0


def test_generator_rejects_unknown_or_drifted_structure():
    with pytest.raises(ValueError):candidate_source(SOURCE.read_text(),'unknown')
    with pytest.raises(ValueError):candidate_source(SOURCE.read_text().replace('ORDERBOOK_DIRECTIONAL_IMBALANCE_CONFIRM_MIN','UNEXPECTED'),'monotonic')


@pytest.mark.parametrize('damage',[None,'legacy','volume','candle'])
def test_corrected_input_audit_checks_raw_multi_page_capture(tmp_path,damage):
    import hashlib,json,sqlite3,zlib
    from platform_v2.tools.research.orderflow_input_audit import aggregate
    (tmp_path/'data').mkdir()
    (tmp_path/'protocol.json').write_text(json.dumps({'start_ms':899999,'end_ms':900000}))
    with sqlite3.connect(tmp_path/'data/trading.sqlite3') as db:
        db.executescript('''CREATE TABLE research_blobs(sha256 TEXT,compressed_json BLOB);
CREATE TABLE research_first_live_decisions(id INTEGER,run_id TEXT,attempt_id TEXT,cycle_key TEXT,payload_json TEXT,system TEXT);
CREATE TABLE decision_observations(id INTEGER,run_id TEXT,attempt_id TEXT,cycle_key TEXT,payload_json TEXT,system TEXT,kind TEXT);
CREATE TABLE market_acquisition_events(id INTEGER,event_key TEXT,kind TEXT,at_ms INTEGER,payload_json TEXT,system TEXT,run_id TEXT,attempt_id TEXT,cycle_key TEXT);''')
        def put(value):
            raw=json.dumps(value).encode();sha=hashlib.sha256(raw).hexdigest()
            db.execute('INSERT INTO research_blobs VALUES(?,?)',(sha,zlib.compress(raw)));return sha
        trades=[{'a':1,'T':100,'q':'3','m':False},{'a':2,'T':899998,'q':'1','m':True}]
        row=aggregate(trades)|{'window_start_ms':0,'window_end_ms':899999,'page_count':2,'completeness':'COMPLETE_CLOSED_WINDOW_V1'}
        if damage=='legacy':row['completeness']='LEGACY_UNKNOWN'
        if damage=='volume':row['buyers']=99
        if damage=='candle':row['window_end_ms']=1799999
        manifest=put({'identity':['binance','crypto','spot','orderflow','BTCUSDT','15m'],'chunks':[put([row])]})
        observed={'record':{'timestamp_ms':899999},'evidence_complete':True,'available_ms':910000,'input_refs':[manifest]}
        text=json.dumps(observed)
        db.execute('INSERT INTO research_first_live_decisions VALUES(1,?,?,?,?,?)',('r','a','c',text,'spot'))
        db.execute('INSERT INTO decision_observations VALUES(1,?,?,?,?,?,?)',('r','a','c',text,'spot','LIVE_OBSERVED'))
        for i,trade in enumerate(trades):
            request={'endpoint':'https://api.binance.com/api/v3/aggTrades','params':{'startTime':['0'],'endTime':['899999']} if i==0 else {'fromId':['2']}}
            response={'request_id':f'req{i}','content_ref':put([trade])}
            for kind,key,payload in [('REQUESTED',f'req{i}',request),('RESPONSE',f'res{i}',response)]:
                db.execute('INSERT INTO market_acquisition_events VALUES(?,?,?,?,?,?,?,?,?)',(2*i+(kind=='RESPONSE'),key,kind,900001,json.dumps(payload),'spot','r','a','c'))
    if damage:
        with pytest.raises(ValueError):audit_complete_inputs(tmp_path)
    else:
        result=audit_complete_inputs(tmp_path)
        assert result['cycles']==1 and result['all_raw_pages_verified']
        assert result['records'][0]['trades']==2 and result['records'][0]['pages']==2
