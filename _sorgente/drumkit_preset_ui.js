// Carica il kit Drums di fabbrica (64 pad, 8 loop ritmici per genere presi dal jukebox) SOLO se il
// kit e' ancora completamente vuoto — mai sovrascrive un kit che l'utente ha gia' costruito o
// ripristinato da autosave/.lpstudio. Va chiamato dopo checkAutosaveOnStartup(), cosi' un eventuale
// ripristino ha gia' avuto la sua occasione di popolare drumKit prima di questo controllo.
let drumKitPresetLoadStarted=false;   // guardia sincrona: evita un doppio giro di decode se la funzione
                                       // venisse mai invocata due volte prima che il primo giro finisca.
async function loadDrumKitPresetIfEmpty(){
  if(typeof DRUM_KIT_PRESET==='undefined'||drumKitPresetLoadStarted) return;
  let empty=true;
  for(let r=0;r<ROWS && empty;r++)for(let c=0;c<COLS;c++) if(drumKit[r][c]){ empty=false; break; }
  if(!empty) return;
  drumKitPresetLoadStarted=true;
  for(const cl of DRUM_KIT_PRESET){
    try{
      const ab=b64ToAb(cl.data); const raw=ab.slice(0);
      const audio=await ac().decodeAudioData(ab);
      drumKit[cl.r][cl.c]={buffer:audio,name:cl.name,raw,mime:cl.mime,gain:1,pitch:0,choke:0,trimStart:0,trimEnd:null};
    }catch(e){}
  }
  if(perfMode==='drums'){ selectPad(selected.r,selected.c); renderAll(); }
  refreshAllLeds();
}
