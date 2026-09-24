import { PiperPlus } from 'piper-plus';
import { S, POS } from './lyric-data.js';

/* ===== 渲染逻辑 ===== */
const LVL={
  n5:['N5','pill n5','wtag n5'],
  n4:['N4','pill n4','wtag n4'],
  n3:['N3','pill n3','wtag n3'],
  n2:['N2','pill n2','wtag n2'],
  n1:['N1','pill n1','wtag n1'],
  '':['NX','pill nx','wtag nx']
};
function lvMeta(lv){return LVL[lv]||LVL[''];}

// 重复词检测：记录词形首次出现位置
const firstSeen={};

// 词性：所有词都显示；只有四类词（动词/形容词/助动词/句型）标注形态
function isFormWord(pos){
  if(!pos) return false;
  return pos.includes('动词')||pos.includes('形容词')||pos.includes('助动词')||pos.includes('句型');
}

// 记录每个词出现过的所有句子（用于多出处）
const wordSents={};
// 每句纯文本（去除ruby标签，供出处显示）
const sentPlain={};
const stripRuby=h=>h.replace(/<ruby>([^<]*)<rt>[\s\S]*?<\/rt><\/ruby>/g,'$1').replace(/<[^>]+>/g,'');
const escAttr=s=>String(s).replace(/&/g,'&amp;').replace(/"/g,'&quot;').replace(/</g,'&lt;');
/** 给片假名 ruby 打上 .ruby-kata，便于单独开关平假名注音 */
function markRubyClasses(html){
  return String(html||'').replace(/<ruby([^>]*)>([^<]*)<rt>([\s\S]*?)<\/rt><\/ruby>/g,(_,attrs,base,rt)=>{
    const bare=String(base).replace(/<[^>]+>/g,'').trim();
    const isKata=/^[\u30a0-\u30ffー゛゜・ゝゞヽヾ]+$/.test(bare);
    const cleaned=String(attrs||'').replace(/\s*class\s*=\s*("[^"]*"|'[^']*'|[^\s>]+)/gi,'');
    const cls=isKata?'ruby-kata':'ruby-kanji';
    return `<ruby${cleaned} class="${cls}">${base}<rt>${rt}</rt></ruby>`;
  });
}
const SPEAK_ICON=`<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M11 5L6 9H3v6h3l5 4V5z"/><path d="M15.5 8.5a4.5 4.5 0 0 1 0 7"/><path d="M18.5 6a8 8 0 0 1 0 12"/></svg>`;
function speakBtn(text, extraClass=''){
  const t=(text||'').trim();
  if(!t) return '';
  return `<button type="button" class="speak${extraClass?' '+extraClass:''}" aria-label="发音" title="发音" data-speak="${escAttr(t)}">${SPEAK_ICON}</button>`;
}
function wordSpeakText(ja, read){
  // piper-plus（OpenJTalk）优先送汉字词形，由词典解析读音/音调；无汉字时用读音或词形
  const j=(ja&&String(ja).trim())||'';
  if(j && /[\u4e00-\u9fff]/.test(j)) return j;
  return (read&&String(read).trim())||j;
}

/* ===== 日语朗读（piper-plus / OpenJTalk）===== */
let piper=null;
let piperInit=null;
let speakAudio=null;
let speakGen=0;

function clearSpeakingUI(){
  document.querySelectorAll('.speak.playing,.speak.loading').forEach(el=>{
    el.classList.remove('playing','loading');
    el.title='发音';
  });
}
function stopSpeak(){
  speakGen++;
  if(speakAudio){
    try{
      speakAudio.pause();
      const src=speakAudio.src;
      speakAudio.removeAttribute('src');
      speakAudio.load();
      if(src) URL.revokeObjectURL(src);
    }catch(_){}
    speakAudio=null;
  }
  clearSpeakingUI();
}
function ensurePiper(){
  if(piper) return Promise.resolve(piper);
  if(piperInit) return piperInit;
  piperInit=PiperPlus.initialize({model:'tsukuyomi'})
    .then(p=>{piper=p; return p;})
    .catch(err=>{piperInit=null; throw err;});
  return piperInit;
}
async function speak(text, btn){
  const t=(text||'').trim();
  if(!t) return;
  stopSpeak();
  const gen=speakGen;
  if(btn){
    btn.classList.add('loading');
    btn.title='加载语音模型…';
  }
  try{
    const eng=await ensurePiper();
    if(gen!==speakGen) return;
    if(btn) btn.title='合成中…';
    const result=await eng.synthesize(t,{language:'ja',lengthScale:1.05});
    if(gen!==speakGen) return;
    const url=URL.createObjectURL(result.toBlob());
    const audio=new Audio(url);
    speakAudio=audio;
    if(btn){
      btn.classList.remove('loading');
      btn.classList.add('playing');
      btn.title='发音';
    }
    const done=()=>{
      if(speakAudio===audio) speakAudio=null;
      URL.revokeObjectURL(url);
      if(btn) btn.classList.remove('playing','loading');
    };
    audio.addEventListener('ended',done);
    audio.addEventListener('error',done);
    await audio.play();
  }catch(err){
    if(btn){
      btn.classList.remove('loading','playing');
      btn.title='发音';
    }
    console.error(err);
    alert('语音合成失败（需联网首次下载 piper-plus 模型，并允许浏览器播放声音）');
  }
}

// 生词总表（去重）
const vocabMap=new Map();
S.forEach((s,si)=>{
  s.ws.forEach(w=>{
    const k=w[0];
    const wobj={ja:w[0],read:w[1],mean:w[2],lv:w[3],note:w[4]||'',sent:si+1};
    if(!vocabMap.has(k)) vocabMap.set(k,wobj);
  });
});

function renderLyrics(){
  const box=document.getElementById('lyrics');
  box.innerHTML='';
  S.forEach((s,si)=>{
    const num=si+1;
    sentPlain[num]=stripRuby(s.jp);
    // 每个词的重复标记
    let whtml='';
    s.ws.forEach(w=>{
      const k=w[0];
      const meta=lvMeta(w[3]);
      const lv=meta[2];
      const isRep=firstSeen[k]!==undefined;
      const repTag=isRep?`<span class="rep">重复·第${firstSeen[k]}处</span>`:'';
      if(!isRep) firstSeen[k]=num;
      const readHtml=`<span class="w-ja">${w[0]}</span>`;
      const p=POS[k]||{pos:'',form:''};
      const posHtml=`<span class="pos">${p.pos||''}</span>`;
      const formTag=(isFormWord(p.pos)&&p.form)?`<span class="pos-f">${p.form}</span>`:'';
      (wordSents[k]=wordSents[k]||[]).push(num);
      const say=wordSpeakText(w[0], w[1]);
      whtml+=`<span class="witem"><button class="wtag ${lv}" data-ja="${escAttr(w[0])}" data-read="${escAttr(w[1]||'')}" data-mean="${escAttr(w[2])}" data-lv="${w[3]||''}" data-note="${escAttr(w[4]||'')}" data-speak="${escAttr(say)}">${readHtml}</button>${speakBtn(say)}${posHtml}${formTag}<span class="w-mean">${w[2]}</span>${repTag}</span>`;
    });
    const plain=sentPlain[num];
    const card=document.createElement('div');
    card.className='card';
    card.id='sent-'+num;
    card.innerHTML=`
      <div class="sline" data-s="${num}">
        <span class="num">${num}</span>
        <div class="jp">${markRubyClasses(s.jp)}</div>
        ${speakBtn(plain)}
        <svg class="chev" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M6 9l6 6 6-6"/></svg>
      </div>
      <div class="detail"><div class="detail-inner">
        <div class="sec"><h4>分词</h4><div class="seg">${s.seg.split('｜').join('<span class="sep">·</span>')}</div></div>
        <div class="sec"><h4>词汇与等级</h4><div class="wlist">${whtml}</div></div>
        <div class="sec"><h4>语法</h4><div class="grammar">${s.gram}</div></div>
        <div class="sec"><h4>中文翻译</h4><div class="tr">${s.tr}</div></div>
      </div></div>`;
    box.appendChild(card);
  });
}

function renderStats(){
  const counts={n5:0,n4:0,n3:0,n2:0,n1:0,'':0};
  vocabMap.forEach(v=>{counts[v.lv in counts?v.lv:'']++;});
  const total=vocabMap.size;
  const el=document.getElementById('statBar');
  const bits=[
    ['n5','N5'],['n4','N4'],['n3','N3'],['n2','N2'],['n1','N1'],['','NX']
  ].filter(([k])=>counts[k]>0)
   .map(([k,label])=>`<span class="pill ${lvMeta(k)[1]}">${label} ${counts[k]}</span>`);
  el.innerHTML=`共 <b>${S.length}</b> 句 · <b>${total}</b> 个生词 · ${bits.join(' ')}`;
}

function renderVocabGroups(){
  const order=['n5','n4','n3','n2','n1',''];
  const groups={n5:[],n4:[],n3:[],n2:[],n1:[],'':[]};
  vocabMap.forEach(v=>{
    const lv=v.lv in groups?v.lv:'';
    groups[lv].push(v);
  });
  const el=document.getElementById('vocabGroups');
  el.innerHTML='';
  order.forEach(lv=>{
    const arr=groups[lv];
    if(!arr.length) return;
    const meta=lvMeta(lv);
    const h=document.createElement('div');
    h.className='vg';
    h.innerHTML=`<h5><span class="pill ${meta[1]}">${meta[0]}</span><span style="color:var(--muted);font-size:12px">${arr.length} 词</span></h5>`;
    const t=document.createElement('div'); t.className='tags';
    arr.forEach(v=>{
      const p=POS[v.ja]||{pos:''};
      const formTag=(isFormWord(p.pos)&&p.form)?`<span class="wform">${p.form}</span>`:'';
      t.innerHTML+=`<span class="witem"><button class="wtag ${lvMeta(v.lv)[2]}" data-ja="${escAttr(v.ja)}" data-read="${escAttr(v.read||'')}" data-mean="${escAttr(v.mean)}" data-lv="${v.lv||''}" data-note="${escAttr(v.note||'')}" data-speak="${escAttr(wordSpeakText(v.ja,v.read))}">${v.ja}<span class="wpos">${p.pos||''}</span>${formTag}</button>${speakBtn(wordSpeakText(v.ja,v.read))}</span>`;
    });
    h.appendChild(t);
    el.appendChild(h);
  });
}

/* ===== 交互 ===== */
const popMask=document.getElementById('popMask'), pop=document.getElementById('pop');
const pJp=document.getElementById('popJp'), pLv=document.getElementById('popLv'), pRead=document.getElementById('popRead'),
      pMean=document.getElementById('popMean'), pSrc=document.getElementById('popSrc'), pNote=document.getElementById('popNote');

document.addEventListener('click',e=>{
  // 发音按钮（句子 / 单词旁）
  const sp=e.target.closest('.speak');
  if(sp){
    e.preventDefault();
    e.stopPropagation();
    speak(sp.dataset.speak||'', sp);
    return;
  }
  // 词汇标签 → 弹窗
  const w=e.target.closest('.wtag');
  if(w){
    const ja=w.dataset.ja;
    pJp.textContent=ja;
    const popSpeak=document.getElementById('popSpeak');
    const say=wordSpeakText(ja, w.dataset.read);
    popSpeak.dataset.speak=say;
    popSpeak.innerHTML=SPEAK_ICON;
    popSpeak.style.display=say?'':'none';
    const meta=lvMeta(w.dataset.lv||'');
    pLv.innerHTML=`<span class="pill ${meta[1]}">${meta[0]}</span>`;
    const p=POS[ja]||{pos:'',form:''};
    document.getElementById('popPos').textContent=p.pos||'—';
    // 形态：仅四类词
    const fw=isFormWord(p.pos);
    const formRow=document.getElementById('popFormRow');
    formRow.style.display=fw?'':'none';
    document.getElementById('popForm').textContent=fw?(p.form||'—'):'';
    // 字典形：仅变体
    const baseRow=document.getElementById('popBaseRow');
    baseRow.style.display=p.base?'':'none';
    document.getElementById('popBase').textContent=p.base||'';
    // 其他形态：四类词且有 forms，排除当前形态
    const formsRow=document.getElementById('popFormsRow');
    const others=(fw&&Array.isArray(p.forms))?p.forms.filter(f=>f[0]!==p.form):[];
    formsRow.style.display=others.length?'':'none';
    document.getElementById('popForms').innerHTML=others.map(f=>`<span class="of"><b>${f[0]}</b>${f[1]}</span>`).join('');
    // 读音：纯平假名/符号隐藏；含汉字或片假名时显示（片假名已转平假名）
    const readRow=document.getElementById('popReadRow');
    const hasCJK=/[\u4e00-\u9fff]/.test(ja), hasKata=/[\u30a0-\u30ff]/.test(ja);
    if((hasCJK||hasKata)&&w.dataset.read){
      readRow.style.display='';
      pRead.textContent=w.dataset.read;
    }else{
      readRow.style.display='none';
    }
    pMean.textContent=w.dataset.mean||'—';
    // 出处：所有出现句，直接写明句子内容
    const sents=(wordSents[ja]||[w.dataset.sent]);
    pSrc.innerHTML=sents.map(n=>`<div class="sent-item"><b>第${n}句</b>${sentPlain[n]||''}</div>`).join('');
    // 说明：与词性/形态/字典形重复的不显示；无说明时隐藏该行
    const note=w.dataset.note||'';
    const noteRow=document.getElementById('popNoteRow');
    const dupNote=/^(字典形|ない形|ます形|て形|た形|ば形|意志形|命令形|可能态|被动态|使役态|使役被动态|否定形|过去形|副词化|假定形|～たい|名词|副词|イ形容词|ナ形容词)/.test(note);
    const showNote=note&&!dupNote;
    noteRow.style.display=showNote?'':'none';
    pNote.textContent=showNote?note:'';
    pop.classList.add('show'); popMask.classList.add('show');
    return;
  }
  // 句子展开
  const line=e.target.closest('.sline');
  if(line){
    const card=line.closest('.card');
    card.classList.toggle('open');
    return;
  }
});

function closePop(){
  pop.classList.remove('show');
  popMask.classList.remove('show');
  stopSpeak();
}
document.getElementById('popClose').addEventListener('click',closePop);
popMask.addEventListener('click',closePop);

document.getElementById('btnAll').addEventListener('click',()=>{
  document.querySelectorAll('.card').forEach(c=>c.classList.add('open'));
});
document.getElementById('btnCollapse').addEventListener('click',()=>{
  document.querySelectorAll('.card').forEach(c=>c.classList.remove('open'));
});

/* ===== 显示设置（振假名 / 片假名→平假名）===== */
const OPT_KEY='jp-lyrics-study:display-opts';
const optRuby=document.getElementById('optRuby');
const optKataRuby=document.getElementById('optKataRuby');
const settingsPanel=document.getElementById('settingsPanel');
const settingsMask=document.getElementById('settingsMask');

function loadOpts(){
  try{
    const raw=localStorage.getItem(OPT_KEY);
    if(!raw) return {ruby:true, kataRuby:false};
    const o=JSON.parse(raw);
    return {
      ruby:o.ruby!==false,
      kataRuby:o.kataRuby===true
    };
  }catch(_){
    return {ruby:true, kataRuby:false};
  }
}
function saveOpts(){
  try{
    localStorage.setItem(OPT_KEY, JSON.stringify({
      ruby:!!optRuby.checked,
      kataRuby:!!optKataRuby.checked
    }));
  }catch(_){}
}
function applyOpts(){
  document.body.classList.toggle('opt-ruby', !!optRuby.checked);
  document.body.classList.toggle('opt-kata-ruby', !!optKataRuby.checked);
  optKataRuby.disabled=!optRuby.checked;
}
function openSettings(){
  settingsPanel.classList.add('show');
  settingsMask.classList.add('show');
}
function closeSettings(){
  settingsPanel.classList.remove('show');
  settingsMask.classList.remove('show');
}
(function initOpts(){
  const o=loadOpts();
  optRuby.checked=o.ruby;
  optKataRuby.checked=o.kataRuby;
  applyOpts();
})();
optRuby.addEventListener('change',()=>{
  applyOpts();
  saveOpts();
});
optKataRuby.addEventListener('change',()=>{
  applyOpts();
  saveOpts();
});
document.getElementById('btnSettings').addEventListener('click',openSettings);
document.getElementById('settingsClose').addEventListener('click',closeSettings);
settingsMask.addEventListener('click',closeSettings);

renderLyrics();
renderStats();
renderVocabGroups();
document.getElementById('popSpeak').innerHTML=SPEAK_ICON;
