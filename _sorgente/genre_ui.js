let newKitBtn=null, draftKitName=null, draftKitOptionEl=null, saveKitBtn=null, delKitBtn=null, customKitOptionEls=[], sel=null, btn=null;
let exportKitBtn=null, importKitBtn=null, kitFileInput=null, stat=null;
let refreshGenreSelectOptions, updateDelKitVisibility, loadGenre, loadCustomKit;   // assegnate dentro l'IIFE (chiudono su sel/customKits)
(function(){
  const box=document.querySelector('.grid-box');
  const bar=document.createElement('div');
  bar.style.cssText='display:flex;gap:10px;align-items:center;margin-bottom:12px;flex-wrap:wrap;padding:10px;background:#181b22;border:1px solid #2c313d;border-radius:10px;max-width:580px';
  const lab=document.createElement('label'); lab.textContent='🎚️ Genere'; lab.style.cssText='font-size:13px;color:#8b93a4';
  sel=document.createElement('select');
  sel.style.cssText='background:#20242e;color:#e8ebf1;border:1px solid #2c313d;border-radius:8px;padding:8px 10px;font-size:13px;min-width:230px';
  Object.keys(GENRES).forEach(k=>{const o=document.createElement('option');o.value=k;o.textContent=k;sel.appendChild(o);});
  btn=document.createElement('button'); btn.textContent='▶ Carica genere';
  btn.style.cssText='background:#4ea1ff;border:1px solid #4ea1ff;color:#04101f;font-weight:600;border-radius:8px;padding:9px 14px;cursor:pointer;font-size:13px';
  stat=document.createElement('span'); stat.style.cssText='font-size:12px;color:#8b93a4;min-width:0;flex:1 1 100%';
  bar.appendChild(lab); bar.appendChild(sel); bar.appendChild(btn);
  newKitBtn=document.createElement('button'); newKitBtn.textContent='+ Nuovo kit';
  newKitBtn.style.cssText='background:#20242e;border:1px solid #2c313d;color:#e8ebf1;border-radius:8px;padding:9px 14px;cursor:pointer;font-size:13px';
  bar.appendChild(newKitBtn);
  newKitBtn.onclick=()=>{
    if(perfMode==='drums'){ stat.textContent='Non disponibile in modalità Drums'; return; }
    const name=prompt('Nome del kit:'); if(!name) return;
    pushUndo();
    for(let r=0;r<ROWS;r++)for(let c=0;c<COLS;c++) clips[r][c]=null;
    recomputeTrackColors(); renderAll(); refreshAllLeds();
    loadedGenreKeyByBank[activeBank]=null; updateSaveModBtnVisibility();   // non e' piu' contenuto di un genere di fabbrica
    draftKitName=name;
    // Voce temporanea "draft" nel <select>, cosi' il nome appena scelto risulta visibilmente
    // selezionato al posto dell'ultimo genere caricato invece di lasciare un residuo fuorviante
    // (es. "Techno Industrial" mentre in realta' si sta costruendo un kit vuoto). Sparisce al
    // primo salvataggio (sostituita dalla voce reale "kit:id") o cambiando selezione a mano.
    if(draftKitOptionEl) draftKitOptionEl.remove();
    draftKitOptionEl=document.createElement('option'); draftKitOptionEl.value='draft'; draftKitOptionEl.textContent=name;
    sel.appendChild(draftKitOptionEl);
    sel.value='draft';
    updateDelKitVisibility();
    stat.textContent='Nuovo kit «'+name+'» — trascina suoni dal catalogo per riempirlo.';
  };
  refreshGenreSelectOptions=function(){
    const prev=sel.value;
    customKitOptionEls.forEach(o=>o.remove());
    customKitOptionEls=[];
    if(customKits.length){
      const sep=document.createElement('option'); sep.disabled=true; sep.textContent='— I tuoi kit —';
      sel.appendChild(sep); customKitOptionEls.push(sep);
      customKits.forEach(k=>{ const o=document.createElement('option'); o.value='kit:'+k.id; o.textContent=k.name; sel.appendChild(o); customKitOptionEls.push(o); });
    }
    if(Array.prototype.some.call(sel.children, o=>o.value===prev)) sel.value=prev;
    updateDelKitVisibility();
  };
  updateDelKitVisibility=function(){ delKitBtn.style.display = sel.value.startsWith('kit:') ? 'inline-block' : 'none'; };
  sel.onchange=()=>{
    if(draftKitOptionEl && sel.value!=='draft'){ draftKitOptionEl.remove(); draftKitOptionEl=null; }
    updateDelKitVisibility();
  };

  saveKitBtn=document.createElement('button'); saveKitBtn.textContent='💾 Salva come kit';
  saveKitBtn.style.cssText=newKitBtn.style.cssText;
  bar.appendChild(saveKitBtn);
  function buildKitSnapshot(name,id){
    const out={id, name, bpm, bars, phraseBars,
      master:audioCtx?+document.getElementById('master').value:1,
      filter:+document.getElementById('filter').value,
      revWet:+document.getElementById('revWet').value, revSize:+document.getElementById('revSize').value,
      dlyWet:+document.getElementById('dlyWet').value, dlyFb:+document.getElementById('dlyFb').value, dlyTime:+document.getElementById('dlyTime').value,
      tracks:tracks.map(t=>({volume:t.volume,muted:t.muted,solo:t.solo,low:t.low||0,high:t.high||0,revSend:t.revSend||0,dlySend:t.dlySend||0})),
      clips:[]};
    for(let r=0;r<ROWS;r++)for(let c=0;c<COLS;c++){ const cl=clips[r][c];
      if(cl&&cl.raw) out.clips.push({r,c,name:cl.name,mime:cl.mime,mode:cl.mode||'loop',trimStart:cl.trimStart||0,trimEnd:cl.trimEnd!=null?cl.trimEnd:null,sourceBpm:cl.sourceBpm||bpm,raw:cl.raw}); }
    return out;
  }
  saveKitBtn.onclick=async ()=>{
    const selectedKit = sel.value.startsWith('kit:') ? customKits.find(k=>k.id===sel.value.slice(4)) : null;
    const name=prompt('Nome del kit:', draftKitName||(selectedKit?selectedKit.name:'Kit personalizzato')); if(!name) return;
    // Se il kit personalizzato attualmente selezionato ha lo stesso nome confermato dall'utente,
    // interpretiamo il salvataggio come un AGGIORNAMENTO di quel kit (stesso id) invece che una
    // nuova voce: kitPut sovrascrive gia' per chiave in IndexedDB, qui basta aggiornare l'array
    // customKits sul posto (niente push) cosi' non compare un doppione nel <select>.
    const updating = !!(selectedKit && name===selectedKit.name);
    const kit=buildKitSnapshot(name, updating?selectedKit.id:newKitId());
    await kitPut(kit);
    if(updating){
      const idx=customKits.findIndex(k=>k.id===kit.id);
      if(idx>=0) customKits[idx]=kit; else customKits.push(kit);
    } else {
      customKits.push(kit);
    }
    if(draftKitOptionEl){ draftKitOptionEl.remove(); draftKitOptionEl=null; }
    refreshGenreSelectOptions();
    sel.value='kit:'+kit.id;
    updateDelKitVisibility();
    stat.textContent='Kit «'+name+'» salvato ✓';
  };

  delKitBtn=document.createElement('button'); delKitBtn.textContent='🗑️ Elimina kit';
  delKitBtn.style.cssText=newKitBtn.style.cssText;
  delKitBtn.style.display='none';
  bar.appendChild(delKitBtn);
  delKitBtn.onclick=async ()=>{
    if(!sel.value.startsWith('kit:')) return;
    const id=sel.value.slice(4);
    await kitDelete(id);
    customKits=customKits.filter(k=>k.id!==id);
    refreshGenreSelectOptions();
    sel.value=Object.keys(GENRES)[0]||'';
    updateDelKitVisibility();
    stat.textContent='Kit eliminato';
  };

  exportKitBtn=document.createElement('button'); exportKitBtn.textContent='📂 Esporta kit';
  exportKitBtn.style.cssText=newKitBtn.style.cssText;
  bar.appendChild(exportKitBtn);
  exportKitBtn.onclick=()=>{
    if(!sel.value.startsWith('kit:')){ stat.textContent='Seleziona prima un kit personalizzato da esportare.'; return; }
    const kit=customKits.find(k=>k.id===sel.value.slice(4)); if(!kit) return;
    const out={version:1,id:kit.id,name:kit.name,bpm:kit.bpm,bars:kit.bars,phraseBars:kit.phraseBars,
      master:kit.master,filter:kit.filter,revWet:kit.revWet,revSize:kit.revSize,dlyWet:kit.dlyWet,dlyFb:kit.dlyFb,dlyTime:kit.dlyTime,
      tracks:kit.tracks,
      clips:kit.clips.map(cl=>({r:cl.r,c:cl.c,name:cl.name,mime:cl.mime,mode:cl.mode,trimStart:cl.trimStart,trimEnd:cl.trimEnd,sourceBpm:cl.sourceBpm,data:abToB64(cl.raw)}))};
    const blob=new Blob([JSON.stringify(out)],{type:'application/json'});
    const a=document.createElement('a'); a.href=URL.createObjectURL(blob);
    a.download=(kit.name.replace(/[^a-z0-9 _-]/gi,'')||'kit')+'.lpkit'; a.click();
    setTimeout(()=>URL.revokeObjectURL(a.href),2000);
  };

  importKitBtn=document.createElement('button'); importKitBtn.textContent='📥 Importa kit';
  importKitBtn.style.cssText=newKitBtn.style.cssText;
  kitFileInput=document.createElement('input'); kitFileInput.type='file'; kitFileInput.accept='.lpkit,application/json'; kitFileInput.style.display='none';
  bar.appendChild(importKitBtn); bar.appendChild(kitFileInput);
  importKitBtn.onclick=()=>kitFileInput.click();
  kitFileInput.onchange=async (e)=>{
    const f=e.target.files[0]; if(!f) return; e.target.value='';
    try{
      const data=JSON.parse(await f.text());
      const id=newKitId();
      const kit={id,name:data.name||'Kit importato',bpm:data.bpm,bars:data.bars,phraseBars:data.phraseBars,
        master:data.master,filter:data.filter,revWet:data.revWet,revSize:data.revSize,dlyWet:data.dlyWet,dlyFb:data.dlyFb,dlyTime:data.dlyTime,
        tracks:data.tracks||[],
        clips:(data.clips||[]).map(cl=>({r:cl.r,c:cl.c,name:cl.name,mime:cl.mime,mode:cl.mode,trimStart:cl.trimStart,trimEnd:cl.trimEnd,sourceBpm:cl.sourceBpm,raw:b64ToAb(cl.data)}))};
      await kitPut(kit);
      customKits.push(kit);
      refreshGenreSelectOptions();
      stat.textContent='Kit «'+kit.name+'» importato ✓';
    }catch(err){ alert('File .lpkit non valido.'); }
  };
  refreshGenreSelectOptions();
  updateDelKitVisibility();
  bar.appendChild(stat);   // in fondo e su riga propria (flex-basis:100%): non deve mai spingere i bottoni
  box.insertBefore(bar, box.firstChild);
  async function loadGenreData(data,label,genreKey){
    stat.textContent='Carico '+label+'…'; await new Promise(r=>setTimeout(r,20));
    pushUndo();
    loadingSet=true;
    await stopAllSmooth(1.2);
    perfMode=null;   // esce dalla modalita' Drums: qui si sta per sostituire clips interi
    bpm=data.bpm||120; document.getElementById('bpm').value=bpm; document.getElementById('bpmVal').textContent=bpm;
    bars=data.bars||4; document.getElementById('bars').value=([1,2,4,8].includes(bars)?bars:4);
    quantMode='off'; document.getElementById('quant').value='off';
    phraseBars=data.phraseBars||bars;
    ac();
    const masterVal=data.master!=null?data.master:1.0;
    document.getElementById('master').value=masterVal; masterGain.gain.value=masterVal;
    const filterVal=data.filter!=null?data.filter:1.0;
    document.getElementById('filter').value=filterVal; masterFilter.frequency.setTargetAtTime(20*Math.pow(1000,filterVal), audioCtx.currentTime, 0.02);
    const revWetVal=data.revWet!=null?data.revWet:0, revSizeVal=data.revSize!=null?data.revSize:2;
    document.getElementById('revWet').value=revWetVal; fxReverbSend.gain.value=revWetVal;
    document.getElementById('revSize').value=revSizeVal; setReverbSize(revSizeVal);
    const dlyWetVal=data.dlyWet!=null?data.dlyWet:0, dlyFbVal=data.dlyFb!=null?data.dlyFb:0.35, dlyTimeVal=data.dlyTime!=null?data.dlyTime:0.5;
    document.getElementById('dlyWet').value=dlyWetVal; fxDelaySend.gain.value=dlyWetVal;
    document.getElementById('dlyFb').value=dlyFbVal; fxDelayFb.gain.value=dlyFbVal;
    document.getElementById('dlyTime').value=dlyTimeVal; fxDelay.delayTime.value=secPerBeat()*dlyTimeVal;
    (data.tracks||[]).forEach((t,c)=>{ if(c<COLS){ const v=t.volume!=null?t.volume:1.0; tracks[c].volume=v;tracks[c].muted=t.muted;tracks[c].solo=t.solo;
      tracks[c].low=t.low||0; tracks[c].high=t.high||0; tracks[c].revSend=t.revSend||0; tracks[c].dlySend=t.dlySend||0;
      tracks[c]._vol.value=v; tracks[c]._m.classList.toggle('on',t.muted); tracks[c]._s.classList.toggle('on',t.solo);} });
    for(let r=0;r<ROWS;r++)for(let c=0;c<COLS;c++) clips[r][c]=null;
    let ok=0;
    for(const cl of data.clips){ try{
      const src = cl.data!=null ? b64ToAb(cl.data) : cl.raw.slice(0);
      const raw = src.slice(0);
      const audio=await ac().decodeAudioData(src);
      const nc={buffer:audio,name:cl.name,raw,mime:cl.mime,mode:cl.mode||'loop',sourceBpm:cl.sourceBpm||data.bpm,trimStart:cl.trimStart||0,trimEnd:cl.trimEnd!=null?cl.trimEnd:null};
      // Se questo pad ha una modifica salvata per QUESTO genere (vedi saveGenreOverride), la applica
      // sopra ai valori di fabbrica - non tocca altri generi che riusano lo stesso suono.
      if(genreKey){
        const ovr=genreOverrides[genreKey+'|'+cl.r+'|'+cl.c];
        if(ovr){
          nc.trimStart=ovr.trimStart||0; nc.trimEnd=ovr.trimEnd!=null?ovr.trimEnd:null; nc.pitch=ovr.pitch||0;
          if(ovr.sourceBpm!=null) nc.sourceBpm=ovr.sourceBpm;
          if(ovr.reversed){ nc.origBuffer=audio; nc.revBuffer=reversedBuffer(audio); nc.buffer=nc.revBuffer; nc.reversed=true; }
        }
      }
      clips[cl.r][cl.c]=nc;
      ok++;
    }catch(e){} }
    selectPad(selected.r,selected.c);   // riaggiorna il pannello (taglio/reverse/pitch) sul pad gia' selezionato, non solo la griglia
    applyMix(); applyTrackFX(); recomputeTrackColors(); renderAll(); refreshAllLeds(); updatePerfModeUI();
    loadingSet=false;
    doAutosave();
    loadedGenreKeyByBank[activeBank]=genreKey||null; updateSaveModBtnVisibility();
    stat.textContent=label+' ✓ ('+ok+' loop)';
  }
  loadGenre=async function(key){ const data=GENRES[key]; if(!data) return; await loadGenreData(data,key,key); };
  loadCustomKit=async function(id){ const kit=customKits.find(k=>k.id===id); if(!kit) return; await loadGenreData(kit,kit.name,null); };
  btn.onclick=()=>{
    if(sel.value.startsWith('kit:')) return loadCustomKit(sel.value.slice(4));
    else return loadGenre(sel.value);
  };
})();
