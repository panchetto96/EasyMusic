let catalogRowEls={};   // "genere|indice" -> elemento riga, per lo stato "in ascolto" (previewing)
let catalogBoxEl=null;   // il pannello .catalog-box stesso, per i test (trascinamento pad->catalogo)
// Colore per categoria nel catalogo: stesso hash deterministico su tutti i generi (es. "Drums" sempre
// lo stesso colore ovunque compaia), riusando la stessa tavolozza trackColors gia' usata per le colonne
// della griglia — coerenza visiva, non serve una mappa fissa categoria->colore da mantenere a mano.
function catalogCategoryColor(cat){
  let h=0; for(let i=0;i<cat.length;i++) h=(h*31+cat.charCodeAt(i))|0;
  return trackColors[Math.abs(h)%trackColors.length];
}
(function(){
  if(typeof GENRES==='undefined') return;
  const wrap=document.querySelector('.wrap');
  const box=document.createElement('div'); box.className='panel catalog-box';
  catalogBoxEl=box;
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
        const catColor=catalogCategoryColor(cat);
        const catBlock=document.createElement('div'); catBlock.style.cssText='margin:6px 0 0 8px;border-left:2px solid '+catColor+';padding-left:6px';
        const catLab=document.createElement('div'); catLab.textContent=cat;
        catLab.style.cssText='color:'+catColor+';font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:.4px;margin-bottom:2px';
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
  // Ctrl+trascina un pad DENTRO il catalogo per svuotarlo (rimuove il suono dalla griglia) — direzione
  // inversa del piazzamento catalogo->pad. Vale ovunque nel pannello (righe, etichette, spazio vuoto),
  // non solo su una riga precisa: pointerup bubbla fino a box comunque.
  box.onpointerenter=()=>{ if(dragSource && dragSource.kind==='pad') box.classList.add('dragover'); };
  box.onpointerleave=()=>{ box.classList.remove('dragover'); };
  box.onpointerup=()=>{
    box.classList.remove('dragover');
    if(dragSource && dragSource.kind==='pad'){
      const {r,c}=dragSource; dragSource=null;
      padEls[r][c].classList.remove('dragging');
      clearGridPad(r,c);
    }
  };
  wrap.appendChild(box);
})();
