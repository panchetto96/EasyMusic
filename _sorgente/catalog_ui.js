let catalogRowEls={};   // "genere|indice" -> elemento riga, per lo stato "in ascolto" (previewing)
(function(){
  if(typeof GENRES==='undefined') return;
  const wrap=document.querySelector('.wrap');
  const box=document.createElement('div'); box.className='panel catalog-box';
  const h=document.createElement('h2'); h.textContent='🗂️ Catalogo suoni'; box.appendChild(h);
  const hint=document.createElement('div'); hint.className='hint'; hint.style.marginBottom='8px';
  hint.textContent="Click = ascolto rapido. Ctrl+trascina su un pad per metterlo li'.";
  box.appendChild(hint);
  Object.keys(GENRES).forEach(genre=>{
    const det=document.createElement('details');
    const sum=document.createElement('summary'); sum.textContent=genre; det.appendChild(sum);
    const groups={};   // categoria -> <div> contenitore righe
    (GENRES[genre].clips||[]).forEach((cl,idx)=>{
      const cat=categoryOf(cl.name);
      if(!groups[cat]){
        const catBlock=document.createElement('div'); catBlock.style.cssText='margin:6px 0 0 8px';
        const catLab=document.createElement('div'); catLab.textContent=cat;
        catLab.style.cssText='color:var(--dim);font-size:11px;text-transform:uppercase;letter-spacing:.4px;margin-bottom:2px';
        catBlock.appendChild(catLab);
        groups[cat]=catBlock; det.appendChild(catBlock);
      }
      const row=document.createElement('div'); row.className='cat-row'; row.textContent=cl.name;
      row.onpointerdown=(e)=>{ if(e.ctrlKey){ e.preventDefault(); stopCatalogPreview(); dragSource={kind:'catalog',genre,idx}; } };
      row.onclick=async (e)=>{
        if(e&&e.ctrlKey) return;   // Ctrl+clic ferma/arma solo il trascinamento (onpointerdown sopra): non deve anche avviare un'anteprima
        const key=genre+'|'+idx;
        const wasThis = previewSrc && previewSrc.key===key;
        await previewCatalogClip(genre,idx);
        Object.keys(catalogRowEls).forEach(k=>catalogRowEls[k].classList.remove('previewing'));
        if(!wasThis && previewSrc && previewSrc.key===key) row.classList.add('previewing');
      };
      catalogRowEls[genre+'|'+idx]=row;
      groups[cat].appendChild(row);
    });
    box.appendChild(det);
  });
  wrap.appendChild(box);
})();
