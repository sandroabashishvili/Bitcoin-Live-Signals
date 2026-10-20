"""Private persistence and clock adapters for the current raw-market Spot engine."""


import copy
import dataclasses
import json
from datetime import datetime, UTC


def plain(value):
    if dataclasses.is_dataclass(value):value=dataclasses.asdict(value)
    return json.loads(json.dumps(value,allow_nan=False))


class SpotStore:
    def __init__(self,output):self.output=output;self.docs={};self.events=[]
    def documents(self,family):return [(date,rows) for (f,date),rows in sorted(self.docs.items()) if f==family]
    def all(self,family):return [r for date,rows in self.documents(family) for r in rows]
    def write(self,family,date,value,key=None):
        row=plain(value);rows=self.docs.setdefault((family,date),[])
        if key:
            index=next((i for i,r in enumerate(rows) if r.get(key)==row.get(key)),None)
            if index is None:rows.append(row)
            else:rows[index]=row
        else:rows.append(row)
        self.events.append({'family':family,'date':date,'row':copy.deepcopy(row)})
        return self.output/'replay.sqlite3'


class NativeAccountAdapter:
    def _patch(self):
            from platform_v2.spot.services.account import position_state_service,position_runtime_service,position_batch_update_service
            from platform_v2.spot.services.signal import signal_runtime_service
            from platform_v2.spot.services.permission import signal_permission_runtime_service,denied_entry_runtime_service
            from platform_v2.spot.services.trading import order_execution_service
            position_state_service.load_family_documents=self.store.documents
            position_runtime_service.load_family_rows_all=self.store.all
            signal_runtime_service.load_family_rows_all=self.store.all
            writers={'write_position_record':('positions','position_id'),'write_signal_record':('signals','timestamp_ms'),
                     'write_denied_entry_record':('denied_entries',None),'write_order_record':('orders',None),
                     'write_force_close_record':('force_closes',None)}
            for module in (position_runtime_service,position_batch_update_service,signal_runtime_service,signal_permission_runtime_service,denied_entry_runtime_service):
                for function,(family,key) in writers.items():
                    if hasattr(module,function):
                        def write(*,date_iso,family=family,key=key,**kw):
                            return self.store.write(family,date_iso,next(iter(kw.values())),key)
                        setattr(module,function,write)
            signal_permission_runtime_service.utc_now_ms=lambda:self.clock
            order_execution_service.utc_now_ms=lambda:self.fill_clock
            replay=self
            class Clock(datetime):
                @classmethod
                def now(cls,tz=None):
                    value=cls.fromtimestamp(replay.clock/1000,UTC)
                    return value.astimezone(tz) if tz else value.replace(tzinfo=None)
            for module in (position_state_service,position_runtime_service,position_batch_update_service,signal_permission_runtime_service):
                module.datetime=Clock

    def latest(self):return [plain(p) for p in self.position_state.load_latest_positions(as_of_date_iso=self.date)]

    def accounting(self):
            from platform_v2.spot.services.account.fee_service import FeeService
            positions=self.position_state.load_latest_positions(as_of_date_iso=self.date)
            opens=[p for p in positions if p.is_open];closed=[p for p in positions if p.is_closed]
            net=sum(FeeService.net_pnl_value(p) for p in closed)
            fees=FeeService.open_entry_fees_total(opens)
            unrealized=sum(float(p.unrealized_pnl or 0) for p in opens)
            state=self.portfolio_state.build_state(as_of_date_iso=self.date)
            return {'closed_net_pnl':round(net,2),'equity':round(self.settings.DEFAULT_STARTING_BALANCE+net-fees+unrealized,2),
                    'unrealized_pnl':round(unrealized,2),'available_balance':state.available_balance,
                    'reserved':state.current_open_exposure,'open_positions':len(opens),'closed_positions':len(closed),
                    'total_positions':len(positions),'open_entry_fees':fees}
