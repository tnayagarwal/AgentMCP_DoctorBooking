import React, { useState, useEffect, useRef } from 'react';
import { createRoot } from 'react-dom/client';
import axios from 'axios';
import './styles.css';

const API = 'http://localhost:8000';

function Chat({ messages, onSend, placeholder = 'Type a message...' }){
  const [input, setInput] = useState('');
  const feedRef = useRef(null);
  useEffect(()=>{ feedRef.current?.scrollTo(0, feedRef.current.scrollHeight); }, [messages]);
  return (
    <div className="chat">
      <div className="chat-feed" ref={feedRef}>
        {messages.map((m,i)=> (<div key={i} className={`msg ${m.role}`}>{m.text}</div>))}
      </div>
      <div className="chat-input">
        <input value={input} onChange={e=>setInput(e.target.value)} placeholder={placeholder} onKeyDown={e=>{if(e.key==='Enter'){onSend(input); setInput('');}}}/>
        <button onClick={()=>{onSend(input); setInput('');}}>Send</button>
      </div>
    </div>
  );
}

function BookingPanel({ doctorId, setDoctorId, date, setDate, slots, setSlots, slot, setSlot, onBooked }){
  const normalizeDate = (d) => {
    if(!d) return d;
    if(/^\d{2}-\d{2}-\d{4}$/.test(d)){
      const [dd,mm,yyyy] = d.split('-');
      return `${yyyy}-${mm}-${dd}`;
    }
    if(/^\d{4}-\d{2}-\d{2}$/.test(d)) return d;
    const parsed = new Date(d);
    if(!isNaN(parsed.getTime())) return parsed.toISOString().slice(0,10);
    return d;
  };
  const onCheck = async () => {
    const iso = normalizeDate(date);
    try{
      const res = await axios.get(`${API}/availability/${doctorId}/${iso}`);
      setSlots(res.data);
      if(res.data.length === 0){ alert(`No slots for ${iso}. Try another date.`);} else { alert(`Found ${res.data.length} slot(s) for ${iso}.`); }
    }catch(e){
      alert('Failed to load slots.');
    }
  };
  const onBook = async () => {
    if(!slot) return;
    const [st, et] = slot.split('-');
    const iso = normalizeDate(date);
    const payload = { patient_id: 1, start_time: st, end_time: et, reason: 'UI booking' };
    try {
      const res = await axios.post(`${API}/book/${doctorId}/${iso}`, payload);
      onBooked(res.data.appointment_id);
    } catch(e) {
      onBooked(null, e?.response?.data?.detail || 'error');
    }
  };
  return (
    <div className="panel">
      <h3>Book Appointment</h3>
      <div className="field"><label>Doctor ID</label><input type="number" value={doctorId} onChange={e=>setDoctorId(parseInt(e.target.value||'1'))}/></div>
      <div className="field"><label>Date</label><input type="text" value={date} onChange={e=>setDate(e.target.value)} placeholder="YYYY-MM-DD or DD-MM-YYYY"/></div>
      <button className="btn" onClick={onCheck}>List Slots</button>
      <div className="list" style={{marginTop:'.8rem'}}>
        {slots.map(s=> (
          <div key={`${s.start_time}-${s.end_time}`} className="item" onClick={()=>setSlot(`${s.start_time}-${s.end_time}`)} style={{cursor:'pointer'}}>
            <span>{s.start_time} - {s.end_time}</span>
            <span className="muted">{s.is_booked? 'Booked':'Open'}</span>
          </div>
        ))}
      </div>
      <div className="field"><label>Selected Slot</label><input value={slot} onChange={e=>setSlot(e.target.value)} placeholder="HH:MM:SS-HH:MM:SS"/></div>
      <button className="btn ok" onClick={onBook}>Book</button>
    </div>
  );
}

function Suggestions({ suggestions, onPickSlot }){
  if(!suggestions || (!suggestions.results?.length && !suggestions.alternatives?.length)) return null;
  return (
    <div className="panel" style={{marginTop:'.8rem'}}>
      <h3>Suggestions</h3>
      {suggestions.results?.length ? (
        <div className="list">
          {suggestions.results.map((d)=> (
            <div key={`doc-${d.doctor_id}`} className="item" style={{display:'block'}}>
              <div style={{display:'flex',justifyContent:'space-between'}}>
                <strong>{d.doctor_name}</strong>
                <span className="muted">{suggestions.date}</span>
              </div>
              <div style={{display:'flex',flexWrap:'wrap',gap:6,marginTop:6}}>
                {d.slots.map((s, idx)=> (
                  <button key={`s-${idx}`} className="btn" onClick={()=>onPickSlot(d.doctor_id, suggestions.date, (s.start_time||'').slice(0,5))}>{(s.start_time||'').slice(0,5)}</button>
                ))}
              </div>
            </div>
          ))}
        </div>
      ) : null}
      {suggestions.alternatives?.length ? (
        <div className="list" style={{marginTop:'.6rem'}}>
          {suggestions.alternatives.map((a, i)=> (
            <div key={`alt-${i}`} className="item" style={{display:'block'}}>
              <div style={{display:'flex',justifyContent:'space-between'}}>
                <strong>{a.doctor_name}</strong>
                <span className="muted">{a.next_available?.date}</span>
              </div>
              <div style={{display:'flex',flexWrap:'wrap',gap:6,marginTop:6}}>
                {a.next_available?.slot ? (
                  <button className="btn" onClick={()=>onPickSlot(a.doctor_id, a.next_available.date, (a.next_available.slot.start_time||'').slice(0,5))}>{(a.next_available.slot.start_time||'').slice(0,5)}</button>
                ) : null}
              </div>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function ReportPanel({ doctorId, setDoctorId }){
  const [prompt, setPrompt] = useState('How many patients visited yesterday?');
  const [result, setResult] = useState('');
  const [history, setHistory] = useState([]);
  const runReport = async () => {
    try{
      const res = await axios.post(`${API}/report`, { prompt, doctor_id: doctorId, channel: 'in_app' });
      setResult(res.data.result);
      const h = await axios.get(`${API}/history`);
      setHistory(h.data);
    }catch(e){
      setResult('Failed to generate summary.');
    }
  };
  useEffect(()=>{ (async()=>{ try{ const h = await axios.get(`${API}/history`); setHistory(h.data);}catch{} })(); },[]);
  return (
    <div className="panel">
      <h3>Doctor Summary</h3>
      <div className="field"><label>Doctor ID</label><input type="number" value={doctorId} onChange={e=>setDoctorId(parseInt(e.target.value||'1'))}/></div>
      <div className="field"><label>Prompt</label><textarea rows={3} value={prompt} onChange={e=>setPrompt(e.target.value)}/></div>
      <button className="btn primary" onClick={runReport}>Generate</button>
      <div className="field" style={{marginTop:'.8rem'}}><label>Result</label><div className="panel" style={{padding:'.6rem'}}>{result}</div></div>
      <div className="field"><label>History</label>
        <div className="list">{history.map(h=> (<div key={h.id} className="item"><span>{h.prompt}</span><span className="muted">{h.created_at}</span></div>))}</div>
      </div>
    </div>
  );
}

function PatientApp({ user }){
  const [messages, setMessages] = useState([{role:'agent', text:`Hi ${user.name||'patient'}, you can check availability and book.`}]);
  const [doctorId, setDoctorId] = useState(1);
  const [date, setDate] = useState(new Date(Date.now() + 86400000).toISOString().slice(0,10));
  const [slots, setSlots] = useState([]);
  const [slot, setSlot] = useState('');
  const [agentState, setAgentState] = useState({});
  const [suggestions, setSuggestions] = useState(null);

  const listSlots = async (dId, dDate) => {
    try{
      const res = await axios.get(`${API}/availability/${dId}/${dDate}`);
      setSlots(res.data);
      if(res.data.length){
        const items = res.data.map(s=> `${s.start_time}-${s.end_time}`).join(', ');
        setMessages(m=>[...m,{role:'agent', text:`Slots for ${dDate}: ${items}`}] );
      }else{
        const next = await axios.get(`${API}/availability_next_days/${dId}/${dDate}/7`);
        if(next.data && next.data.length){
          const msg = next.data.map(d=> `${d.date}: ${d.slots.map(s=> s.start_time+'-'+s.end_time).join(' | ')}`).join(' || ');
          setMessages(m=>[...m,{role:'agent', text:`No slots on ${dDate}. Next options: ${msg}`}]);
        }else{
          setMessages(m=>[...m,{role:'agent', text:`No availability in the next 7 days.`}]);
        }
      }
    }catch(e){
      setMessages(m=>[...m,{role:'agent', text:`Failed to load slots.`}]);
    }
  };

  // Suggestions now come from backend via res.data.ui

  const onSend = async (text) => {
    if(!text.trim()) return;
    setMessages(m=>[...m,{role:'user', text},{role:'agent', text:'Processing...'}]);
    try{
      const res = await axios.post(`${API}/agent/patient_chat`, { message: text, state: agentState });
      const reply = res.data.message;
      const newState = res.data.state || {};
      const ui = res.data.ui || null;
      setAgentState(newState);
      if(newState.doctor_id) setDoctorId(newState.doctor_id);
      if(newState.date) setDate(newState.date);
      if(newState.start_time && newState.end_time){
        setSlot(`${newState.start_time}:00-${newState.end_time}:00`.replace('::', ':'));
      }
      if(ui){ setSuggestions(ui); }
      setMessages(m=>[...m.slice(0, m.length-1), {role:'agent', text:reply}]);
      if(newState.doctor_id && newState.date){
        await listSlots(newState.doctor_id, newState.date);
      }
    }catch(e){
      setMessages(m=>[...m.slice(0, m.length-1), {role:'agent', text:'Agent unavailable. Try again.'}]);
    }
  };

  const onPickSlot = async (dId, dDate, startHHMM) => {
    // Sync UI state
    setDoctorId(dId);
    setDate(dDate);
    setSlot(`${startHHMM}:00-${startHHMM}:00`.replace(/:(\d{2})-/, ':$1-').replace('-','-'));
    // Let agent know the time in natural form
    await onSend(startHHMM);
  };

  const onBooked = (id, err) => {
    if(id) setMessages(m=>[...m,{role:'agent', text:`Booked successfully. Appointment ID: ${id}`}] );
    else setMessages(m=>[...m,{role:'agent', text:`Booking failed: ${err}`}]);
  };

  const canConfirm = agentState && agentState.start_time && agentState.date && agentState.doctor_id;

  return (
    <div className="main">
      <div className="card">
        <div className="header"><h2>Patient</h2></div>
        <div className="grid">
          <div>
            <Chat messages={messages} onSend={onSend} placeholder="e.g., book a slot with Dr Ahuja on 27th August at 3pm"/>
            <Suggestions suggestions={suggestions} onPickSlot={onPickSlot}/>
            {canConfirm ? <div style={{marginTop:8}}><button className="btn ok" onClick={()=>onSend('book')}>Confirm Booking</button></div> : null}
          </div>
          <div>
            <BookingPanel doctorId={doctorId} setDoctorId={setDoctorId} date={date} setDate={setDate} slots={slots} setSlots={setSlots} slot={slot} setSlot={setSlot} onBooked={onBooked}/>
          </div>
        </div>
      </div>
    </div>
  );
}

function DoctorApp({ user }){
  const initialId = user?.doctorId ? Number(user.doctorId) : 1;
  const [messages, setMessages] = useState([{role:'agent', text:`Hello Dr. ${user.name||''}. Ask for summaries using the panel.`}]);
  const [doctorId, setDoctorId] = useState(initialId);
  const onSend = async (text) => {
    if(!text.trim()) return;
    setMessages(m=>[...m,{role:'user', text},{role:'agent', text:'Processing...'}]);
    try{
      const r = await axios.post(`${API}/report`, { prompt: text, doctor_id: doctorId, channel: 'in_app' });
      setMessages(m=>[...m.slice(0, m.length-1), {role:'agent', text:r.data.result}]);
    }catch(e){
      setMessages(m=>[...m.slice(0, m.length-1), {role:'agent', text:'Failed to generate summary.'}]);
    }
  };
  return (
    <div className="main"><div className="card"><div className="header"><h2>Doctor</h2></div><div className="grid"><Chat messages={messages} onSend={onSend} placeholder="Ask for a summary..."/><div><ReportPanel doctorId={doctorId} setDoctorId={setDoctorId}/></div></div></div></div>
  );
}

function Login({ onLogin }){
  const [role, setRole] = useState('patient');
  const [name, setName] = useState('');
  const [password, setPassword] = useState('');
  const [hint, setHint] = useState('');
  const [doctors, setDoctors] = useState([]);
  const [patients, setPatients] = useState([]);
  useEffect(()=>{ (async()=>{
    try{ const d = await axios.get(`${API}/doctors`); setDoctors(d.data);}catch{}
    try{ const p = await axios.get(`${API}/patients`); setPatients(p.data);}catch{}
  })(); },[]);
  const normalize = (s) => (s||'').toLowerCase().replace('dr.', '').replace('dr ', '').trim();
  const onChangeName = (val) => {
    setName(val);
    const n = normalize(val);
    const doc = doctors.find(d=> normalize(d.name).includes(n));
    if(doc){ setHint(`Detected doctor: ${doc.name}`); setRole('doctor'); return; }
    const pat = patients.find(p=> (p.name||'').toLowerCase().includes(n));
    if(pat){ setHint(`Detected patient: ${pat.name}`); setRole('patient'); return; }
    setHint('');
  };
  const onContinue = () => {
    onLogin({ role, name, password, doctorId: (role==='doctor' ? (doctors.find(d=> normalize(d.name).includes(normalize(name)))?.doctor_id||1) : undefined) });
  };
  return (
    <div className="main">
      <div className="card" style={{maxWidth:480}}>
        <div className="header"><h2>Sign in</h2></div>
        <div className="role-switch" style={{marginBottom:12}}>
          <select value={role} onChange={e=>setRole(e.target.value)}>
            <option value="patient">Patient</option>
            <option value="doctor">Doctor</option>
          </select>
        </div>
        <div className="field"><label>{role==='doctor' ? 'Doctor name' : 'Patient name'}</label><input value={name} onChange={e=>onChangeName(e.target.value)} placeholder={role==='doctor'? 'Type doctor name (e.g., Ahuja)':'Type patient name'}/></div>
        {hint && <div className="muted" style={{marginBottom:8}}>{hint}</div>}
        <div className="field"><label>Password</label><input type="password" value={password} onChange={e=>setPassword(e.target.value)} placeholder="Password"/></div>
        <button className="btn primary" onClick={onContinue}>Continue</button>
      </div>
    </div>
  );
}

function App(){
  const [user, setUser] = useState(null);
  if(!user) return <Login onLogin={setUser}/>;
  if(user.role === 'patient') return <PatientApp user={user}/>;
  return <DoctorApp user={user}/>;
}

const root = createRoot(document.getElementById('root'));
root.render(<App />);

