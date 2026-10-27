"""One raw OS invocation transcript; no CPU format, completion or authority.

The trusted owner supplies existing bounded connected descriptors. This module
never acquires an actor, adopts a codec, authenticates labels, or interprets output.
"""
from dataclasses import asdict, dataclass
from functools import wraps
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import threading
from time import monotonic_ns

from . import host_clock as clocks

_MAX_INT=(1 << 63)-1


def _integer(value,name,low,high):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(name+' must be an explicit strict bounded integer')
    return value


def _label(value,name):
    if type(value) is not str or re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:/-]{0,191}',value) is None:
        raise ValueError(name+' must be an explicit bounded correlation label')


def _detached(value):
    return json.loads(json.dumps(value,ensure_ascii=False,allow_nan=False))


@dataclass(frozen=True)
class InvocationIdentity:
    """Correlation labels only, never actual actor/package/model provenance."""
    operation_id: str
    request_hash: str
    tested_commit: str
    package_manifest_sha256: str
    run_id: str
    invocation_id: int
    actor_instance_id: str

    def __post_init__(self):
        for name in ('operation_id','run_id','actor_instance_id'):
            _label(getattr(self,name),name)
        for name,size in (('request_hash',64),('tested_commit',40),('package_manifest_sha256',64)):
            value=getattr(self,name)
            if type(value) is not str or re.fullmatch('[0-9a-f]{%d}' % size,value) is None:
                raise ValueError(name+' must be a complete lowercase digest')
        _integer(self.invocation_id,'invocation_id',1,_MAX_INT)


class _NoIOAvailable(ValueError):
    """Normal single-attempt/EOF/budget refusal without another OS operation."""


def _entry(method):
    @wraps(method)
    def call(self, /, *args, **kwargs):
        self._owner()
        if self._busy:
            self._retire('reentrant invocation entry')
            raise ValueError('reentrant invocation entry')
        self._continuity()
        if self._closed or self._failed or self._journal_failed or self._veto:
            raise ValueError('invocation admission is permanently closed or failed')
        self._busy=True
        epoch=self._veto
        try:
            return method(self,epoch,*args,**kwargs)
        except _NoIOAvailable:
            raise
        except BaseException as error:
            self._retire(type(error).__name__)
            raise
        finally:
            self._busy=False
    return call


class InvocationTranscript:
    """One owner, one original request write, finite raw output and new journal.

    Blocking/cancellation and exclusive endpoint ownership remain the caller's
    obligations. Returned raw bytes, ids and brackets never establish completion.
    """
    def __init__(self,input_fd,output_fd,identity,*,request_raw,journal_path,
                 max_output_bytes,max_reads,read_size,host_clock=None):
        binding=clocks._require_binding(host_clock)
        if type(identity) is not InvocationIdentity:
            raise ValueError('exact frozen InvocationIdentity required')
        if type(request_raw) is not bytes or not 1 <= len(request_raw) <= 16384:
            raise ValueError('exact nonempty opaque request bytes up to 16384 required')
        _integer(max_output_bytes,'max_output_bytes',1,16*1024*1024)
        _integer(max_reads,'max_reads',1,65536)
        _integer(read_size,'read_size',1,8192)
        for fd in (input_fd,output_fd):
            _integer(fd,'fd',0,(1 << 31)-1)
            mode=os.fstat(fd).st_mode
            if not (stat.S_ISFIFO(mode) or stat.S_ISSOCK(mode) or stat.S_ISCHR(mode)):
                raise ValueError('connected OS pipe/socket/character descriptors required; no replay file')
        self._thread=threading.get_ident()
        self._identity,self._request=identity,request_raw
        self._clock_domain=binding
        self._clock=monotonic_ns if binding is None else binding
        self._bound_domain,self._bound_clock=binding,self._clock
        self._clock_metadata=clocks._description(binding)
        self._high=None
        self._max_bytes,self._max_reads,self._read_size=max_output_bytes,max_reads,read_size
        self._closed=self._failed=self._journal_failed=self._busy=self._eof=False
        self._veto=0; self._reason='prepared_raw_only'; self._retired_reason=None
        self._dispatch=None; self._dispatch_complete=False
        self._reads=[]; self._bytes=0; self._unknown_consumption=False; self._close_errors=[]
        owned=[]
        try:
            for fd in (input_fd,output_fd):
                duplicate=os.dup(fd); owned.append(duplicate)
                os.set_inheritable(duplicate,False)
                if os.name=='nt':
                    import msvcrt
                    msvcrt.setmode(duplicate,os.O_BINARY)
            self._input_fd,self._output_fd=owned
            self._journal=Path(journal_path).open('xb')
            try:
                self._prepared=dict(kind='prepared',schema=1,identity=asdict(identity),
                    request_raw_hex=request_raw.hex(),request_raw_sha256=hashlib.sha256(request_raw).hexdigest(),
                    requested_bytes=len(request_raw),host_clock=self._clock_metadata,
                    budgets=dict(max_output_bytes=max_output_bytes,max_reads=max_reads,read_size=read_size),
                    provenance='caller-supplied correlation; original raw OS I/O only',
                    authenticated=False,completion_verified=False,availability_interval_ns=None,
                    sample_interval_ns=None,completion_interval_ns=None)
                self._append(self._prepared)
            except BaseException as error:
                try: self._journal.close()
                except BaseException as cleanup_error:
                    error.add_note('owned journal close failed: '+type(cleanup_error).__name__)
                raise
        except BaseException as error:
            for duplicate in owned:
                try: os.close(duplicate)
                except BaseException as cleanup_error:
                    error.add_note('owned duplicate close failed: '+type(cleanup_error).__name__)
            raise

    @property
    def clock_domain(self):
        return self._clock_domain

    def _retire(self,reason):
        self._failed=True; self._veto+=1; self._reason=reason
        if self._retired_reason is None: self._retired_reason=reason

    def _owner(self):
        if threading.get_ident()!=self._thread:
            self._retire('foreign owner thread')
            raise ValueError('original invocation owner thread required')

    def _continuity(self):
        if self._clock_domain is not self._bound_domain or self._clock is not self._bound_clock:
            self._retire('original clock binding replaced')
            raise ValueError('original fixed clock/domain required')

    def _checkpoint(self,epoch):
        self._continuity()
        if self._closed or self._veto!=epoch:
            raise ValueError('invocation vetoed during original I/O')

    def _stamp(self):
        self._continuity()
        now=_integer(self._clock(),'raw host stamp',0,_MAX_INT)
        if self._high is not None and now < self._high:
            raise ValueError('raw host clock regressed')
        self._high=now
        return now

    def _append(self,value):
        raw=(json.dumps(value,ensure_ascii=False,separators=(',',':'),allow_nan=False)+'\n').encode('utf-8')
        try:
            if self._journal.write(raw)!=len(raw): raise OSError('partial invocation journal write')
            self._journal.flush(); os.fsync(self._journal.fileno())
        except BaseException:
            self._journal_failed=True
            raise

    def _record_failure(self,row,error,phase):
        self._retire(phase+' failed')
        row.update(failure_phase=phase,failure_type=type(error).__name__)
        if isinstance(error,OSError): row['errno']=error.errno
        if not self._journal_failed:
            try: self._append(row)
            except BaseException as journal_error:
                row['failure_journal_error_type']=type(journal_error).__name__

    @_entry
    def dispatch_once(self,epoch):
        if self._dispatch is not None:
            raise _NoIOAvailable('original dispatch already attempted; no resume or resend')
        # Reserve before the first clock and before every possible side effect.
        row=dict(kind='dispatch_started',outcome='started_unknown',requested_bytes=len(self._request),
            raw_hex=self._request.hex(),raw_sha256=hashlib.sha256(self._request).hexdigest(),
            started_marker_ns=None,write_attempted=False,write_returned=False,bytes_written=None,
            raw_write_call_bracket_ns=None,write_call_interval_ns=None)
        self._dispatch=row; self._failed=True
        phase='marker_stamp'
        try:
            row['started_marker_ns']=self._stamp()
            phase='started_journal'; self._append(row)  # flush + fsync before the sole os.write.
            self._checkpoint(epoch)
            phase='before_write_stamp'; begin=self._stamp()
            row['raw_write_call_bracket_ns']=[begin,None]
            self._checkpoint(epoch)
            phase='write'; row['write_attempted']=True
            count=os.write(self._input_fd,self._request)
            row['write_returned']=True
            row['bytes_written']=_integer(count,'returned write count',0,len(self._request))
            row.update(kind='dispatch_result',outcome='written' if count==len(self._request) else 'partial_unknown')
            phase='after_write_stamp'; row['raw_write_call_bracket_ns'][1]=self._stamp()
            if count!=len(self._request):
                phase='partial_write'
                raise OSError('partial original dispatch; remainder prohibited')
            self._checkpoint(epoch)
            phase='result_journal'; self._append(row)
            self._checkpoint(epoch)
        except BaseException as error:
            self._record_failure(row,error,phase)
            raise
        self._dispatch_complete=True; self._failed=False; self._reason='dispatched_raw_only'
        return _detached(row)

    @_entry
    def read_once(self,epoch):
        if not self._dispatch_complete:
            raise _NoIOAvailable('fully recorded successful original dispatch required before output read')
        if self._eof or self._bytes>=self._max_bytes or len(self._reads)>=self._max_reads:
            raise _NoIOAvailable('original EOF or read/byte budget reached; no extra read')
        requested=min(self._read_size,self._max_bytes-self._bytes)
        row=dict(kind='read_started_unknown',read_index=len(self._reads),stream_start=self._bytes,
            requested_bytes=requested,read_attempted=False,raw_hex=None,returned_bytes=None,
            raw_read_call_bracket_ns=[None,None],read_call_interval_ns=None,
            availability_interval_ns=None,sample_interval_ns=None,completion_interval_ns=None)
        self._reads.append(row); self._failed=True
        phase='before_read_stamp'
        try:
            row['raw_read_call_bracket_ns'][0]=self._stamp()
            phase='read_started_journal'; self._append(row)
            self._checkpoint(epoch)
            phase='read'; row['read_attempted']=True
            try:
                raw=os.read(self._output_fd,requested)
            except BlockingIOError:
                raw,kind=b'','empty'
            else:
                if type(raw) is not bytes or len(raw)>requested:
                    raise ValueError('unexpected original OS read result')
                kind='data' if raw else 'eof'
            # Every returned byte/count is recorded before the post-I/O stamp.
            row.update(kind=kind,raw_hex=raw.hex(),returned_bytes=len(raw),stream_end=self._bytes+len(raw))
            self._bytes+=len(raw)
            if kind=='eof': self._eof=True
            phase='after_read_stamp'; row['raw_read_call_bracket_ns'][1]=self._stamp()
            self._checkpoint(epoch)
            phase='read_result_journal'; self._append(row)
            self._checkpoint(epoch)
        except BaseException as error:
            if row['read_attempted'] and row['returned_bytes'] is None:
                self._unknown_consumption=True
            self._record_failure(row,error,phase)
            raise
        self._failed=False; self._reason='output_raw_only'
        return _detached(row)

    def snapshot(self):
        """Detached raw diagnostics; valid after close/failure, never a model proof."""
        self._owner()
        return _detached(dict(schema=1,identity=asdict(self._identity),prepared=self._prepared,
            request_raw_hex=self._request.hex(),request_raw_sha256=hashlib.sha256(self._request).hexdigest(),
            dispatch=self._dispatch,dispatch_recorded_successfully=self._dispatch_complete,
            reads=self._reads,bytes_read=self._bytes,
            bytes_read_scope='known returned prefix only; unknown consumption is never counted as zero',
            unknown_consumption=self._unknown_consumption,eof=self._eof,closed=self._closed,
            failed=self._failed or bool(self._veto),journal_failed=self._journal_failed,
            reason=self._retired_reason if self._retired_reason is not None else self._reason,
            veto_generation=self._veto,
            budgets=dict(max_output_bytes=self._max_bytes,max_reads=self._max_reads,read_size=self._read_size),
            host_clock=self._clock_metadata,host_time_high_water_ns=self._high,
            clock_binding_continuity=(self._clock_domain is self._bound_domain and self._clock is self._bound_clock),
            close_errors=self._close_errors,authenticated=False,completion_verified=False,
            availability_interval_ns=None,sample_interval_ns=None,completion_interval_ns=None))

    def close(self):
        """Close only owned duplicates/journal, once; never resume or replay I/O."""
        self._owner()
        if self._busy:
            self._retire('reentrant close')
            raise ValueError('close must wait until the owner operation unwinds')
        if self._closed: return
        self._closed=True
        first=None
        for close in (lambda:os.close(self._input_fd),lambda:os.close(self._output_fd),self._journal.close):
            try: close()
            except BaseException as error:
                self._close_errors.append(type(error).__name__)
                if first is None: first=error
        if first is not None:
            self._retire('owned close failed')
            raise first


__all__=['InvocationIdentity','InvocationTranscript']
