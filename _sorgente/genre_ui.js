(function(){
  const box=document.querySelector('.grid-box');
  const bar=document.createElement('div');
  bar.style.cssText='display:flex;gap:10px;align-items:center;margin-bottom:12px;flex-wrap:wrap;padding:10px;background:#181b22;border:1px solid #2c313d;border-radius:10px';
  const lab=document.createElement('label'); lab.textContent='🎚️ Genere'; lab.style.cssText='font-size:13px;color:#8b93a4';
  const sel=document.createElement('select');
  sel.style.cssText='background:#20242e;color:#e8ebf1;border:1px solid #2c313d;border-radius:8px;padding:8px 10px;font-size:13px;min-width:230px';
  Object.keys(GENRES).forEach(k=>{const o=document.createElement('option');o.value=k;o.textContent=k;sel.appendChild(o);});
  const btn=document.createElement('button'); btn.textContent='▶ Carica genere';
  btn.style.cssText='background:#4ea1ff;border:1px solid #4ea1ff;color:#04101f;font-weight:600;border-radius:8px;padding:9px 14px;cursor:pointer;font-size:13px';
  const stat=document.createElement('span'); stat.style.cssText='font-size:12px;color:#8b93a4';
  bar.appendChild(lab); bar.appendChild(sel); bar.appendChild(btn); bar.appendChild(stat);
  box.insertBefore(bar, box.firstChild);
  async function loadGenre(key){
    const data=GENRES[key]; if(!data) return;
    stat.textContent='Carico '+key+'…'; await new Promise(r=>setTimeout(r,20));
    pushUndo();
    await stopAllSmooth(1.2);
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
    (data.tracks||[]).forEach((t,c)=>{ if(c<COLS){ const v=t.volume!=null?t.volume:1.0; tracks[c].volume=v;tracks[c].muted=t.muted;tracks[c].solo=t.solo; tracks[c]._vol.value=v; tracks[c]._m.classList.toggle('on',t.muted); tracks[c]._s.classList.toggle('on',t.solo);} });
    for(let r=0;r<ROWS;r++)for(let c=0;c<COLS;c++) clips[r][c]=null;
    let ok=0;
    for(const cl of data.clips){ try{ const ab=b64ToAb(cl.data); const raw=ab.slice(0); const audio=await ac().decodeAudioData(ab); clips[cl.r][cl.c]={buffer:audio,name:cl.name,raw,mime:cl.mime,mode:cl.mode||'loop',sourceBpm:data.bpm,trimStart:cl.trimStart||0,trimEnd:cl.trimEnd!=null?cl.trimEnd:null}; ok++; }catch(e){} }
    applyMix(); recomputeTrackColors(); renderAll(); refreshAllLeds();
    doAutosave();
    stat.textContent=key+' ✓ ('+ok+' loop)';
  }
  btn.onclick=()=>loadGenre(sel.value);
})();
