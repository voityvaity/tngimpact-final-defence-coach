const $=id=>document.getElementById(id);
const I18N=window.FDC_I18N;
const supportedLanguages=['en','ha','yo','ig','sw','zu'];
const speechLanguages={en:'en-US',ha:'ha-NG',yo:'yo-NG',ig:'ig-NG',sw:'sw-KE',zu:'zu-ZA'};
const examples={
 en:{topic:'AI-assisted crop disease detection for smallholder farmers',context:'This project explores a lightweight image-based AI workflow that can help smallholder farmers identify visible crop disease symptoms earlier. It focuses on mobile access, low-resource settings and clear next-step guidance without replacing agricultural experts.',answer:'The main problem is delayed identification of visible crop disease symptoms. Smallholder farmers may not have immediate access to an expert, so the project provides an earlier signal. The goal is not to replace an agronomist but to help a farmer decide when to seek support sooner. A key limitation is that image quality and local disease variation can affect the result.'},
 ha:{topic:'AI wajen taimakawa ƙananan manoma gano cututtukan amfanin gona',context:'Wannan aikin yana nazarin amfani da AI mai sauƙi wajen taimakawa ƙananan manoma su gano alamun cututtukan amfanin gona daga hotuna da wuri, musamman a wuraren da kayan aiki suke da ƙaranci.',answer:'Babban matsalar ita ce jinkirin gano alamun cutar amfanin gona. Wasu ƙananan manoma ba sa samun ƙwararren noma nan take, saboda haka aikin yana bayar da alamar farko. Manufar ba ita ce maye gurbin ƙwararre ba, sai dai taimakawa manomi ya san lokacin neman ƙarin taimako.'},
 yo:{topic:'Lílo AI láti ṣèrànwọ́ fún àwọn agbẹ kékeré láti mọ àrùn irugbin',context:'Iṣẹ́ yìí ń ṣàyẹ̀wò bí AI tó rọrùn ṣe lè lo fọ́tò láti ran àwọn agbẹ kékeré lọ́wọ́ láti rí àmì àrùn irugbin ní kutukutu, pàápàá ní ibi tí ohun èlò kò pọ̀.',answer:'Ìṣòro pàtàkì ni pé a máa ń pẹ́ kí a tó mọ àmì àrùn irugbin. Ọ̀pọ̀ agbẹ kékeré kò ní amòye nítòsí, nítorí náà iṣẹ́ yìí fẹ́ fún wọn ní ìkìlọ̀ àkọ́kọ́. Kì í ṣe láti rọ́pò amòye, bí kò ṣe láti mọ ìgbà tí wọ́n yẹ kí wọ́n wá ìrànlọ́wọ́.'},
 ig:{topic:'Iji AI nyere obere ndị ọrụ ugbo aka ịchọpụta ọrịa ihe ọkụkụ',context:'Ọrụ a na-enyocha otu AI dị mfe nwere ike isi jiri foto nyere obere ndị ọrụ ugbo aka ịchọpụta akara ọrịa ihe ọkụkụ n’oge, karịchaa n’ebe akụrụngwa dị ntakịrị.',answer:'Nsogbu bụ na a na-achọpụta ọrịa ihe ọkụkụ n’oge na-adịghị mma. Ụfọdụ obere ndị ọrụ ugbo enweghị ọkachamara nso, ya mere usoro a na-enye akara mbụ. Ebumnuche abụghị dochie ọkachamara kama inyere onye ọrụ ugbo mara mgbe ọ kwesịrị ịchọ enyemaka.'},
 sw:{topic:'AI kusaidia wakulima wadogo kutambua magonjwa ya mazao',context:'Mradi huu unachunguza mfumo mwepesi wa AI unaotumia picha kusaidia wakulima wadogo kutambua dalili za magonjwa ya mazao mapema, hasa katika mazingira yenye rasilimali chache.',answer:'Tatizo kuu ni kuchelewa kutambua dalili za magonjwa ya mazao. Wakulima wadogo wanaweza kukosa mtaalamu karibu, kwa hiyo mfumo huu unatoa ishara ya mapema. Lengo si kuchukua nafasi ya mtaalamu bali kusaidia mkulima kujua wakati wa kutafuta msaada zaidi.'},
 zu:{topic:'Ukusebenzisa i-AI ukusiza abalimi abancane ukubona izifo zezitshalo',context:'Le phrojekthi ihlola indlela elula ye-AI esebenzisa izithombe ukusiza abalimi abancane ukubona izimpawu zezifo zezitshalo kusenesikhathi, ikakhulukazi ezindaweni ezinezinsiza ezincane.',answer:'Inkinga enkulu ukubambezeleka ekuboneni izimpawu zezifo zezitshalo. Abalimi abancane bangase bangabi nochwepheshe eduze, ngakho uhlelo lunikeza isexwayiso sokuqala. Inhloso akukhona ukufaka uchwepheshe esikhundleni kodwa ukusiza umlimi azi ukuthi kufanele afune nini usizo olwengeziwe.'}
};
let state={questions:[],currentIndex:0,records:{},health:null,lastLanguage:'en'};
let recognition=null;

function lang(){return $('language').value||'en'}
function t(){return I18N[lang()]||I18N.en}
function trFor(code){return I18N[code]||I18N.en}
function escapeHtml(value){const div=document.createElement('div');div.textContent=value??'';return div.innerHTML}
function wordsCount(value){const s=(value||'').trim();return s?s.split(/\s+/).length:0}
function hasPanelWork(){return state.questions.length>0||Object.keys(state.records).length>0}
function hasSessionWork(){return hasPanelWork()||$('topic').value.trim()||$('context').value.trim()||$('answer').value.trim()}

function applyLanguage(){
 const tr=t();document.documentElement.lang=lang();
 document.querySelectorAll('[data-i18n]').forEach(el=>{const key=el.dataset.i18n;if(tr[key]!==undefined)el.textContent=tr[key]});
 document.querySelectorAll('[data-i18n-placeholder]').forEach(el=>{const key=el.dataset.i18nPlaceholder;if(tr[key]!==undefined)el.placeholder=tr[key]});
 if($('dictateBtn').disabled)$('dictateBtn').title=tr.voiceUnavailable;
 updateMode();renderQuestions();renderSelected();updateProgress();renderExistingResult();
}

function persistRaw(){
 try{sessionStorage.setItem('fdc-v22',JSON.stringify({topic:$('topic').value,context:$('context').value,language:lang(),questions:state.questions,currentIndex:state.currentIndex,records:state.records}))}catch(_){ }
}
function restore(){
 try{
  const saved=JSON.parse(sessionStorage.getItem('fdc-v22')||'{}');
  if(supportedLanguages.includes(saved.language))$('language').value=saved.language;
  $('topic').value=saved.topic||'';$('context').value=saved.context||'';
  state.questions=Array.isArray(saved.questions)?saved.questions:[];
  state.currentIndex=Number.isInteger(saved.currentIndex)?saved.currentIndex:0;
  state.records=saved.records&&typeof saved.records==='object'?saved.records:{};
 }catch(_){ }
 state.lastLanguage=lang();
}
function saveCurrentAnswer(doPersist=true){
 const item=state.questions[state.currentIndex];if(!item||!$('answer'))return;
 const answer=$('answer').value;
 if(answer||state.records[item.id])state.records[item.id]={...(state.records[item.id]||{}),answer};
 if(doPersist)persistRaw();
}

async function postJSON(url,payload){
 if(!navigator.onLine)throw new Error(t().offlineError);
 let response;
 try{response=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)})}catch(_){throw new Error(t().requestFailed)}
 let data={};try{data=await response.json()}catch(_){ }
 if(!response.ok)throw new Error(data.detail||t().requestFailed);
 return data;
}

function clearPanel(clearResearch=true){
 state.questions=[];state.currentIndex=0;state.records={};$('answer').value='';
 $('questionsCard').classList.add('hidden');$('answerCard').classList.add('hidden');$('resultCard').classList.add('hidden');$('sessionComplete').classList.add('hidden');
 if(clearResearch){$('topic').value='';$('context').value='';$('fileName').textContent='';$('fileStatus').textContent=''}
 updateCounts();updateProgress();persistRaw();
}
function confirmAndClearPanel(){if(!hasPanelWork())return true;if(!confirm(t().resetConfirm))return false;clearPanel(false);return true}
function fillExample(){const ex=examples[lang()]||examples.en;$('topic').value=ex.topic;$('context').value=ex.context;$('fileName').textContent='';$('fileStatus').textContent='';updateCounts();persistRaw()}
function useExample(){if(!confirmAndClearPanel())return;fillExample()}
async function guidedDemo(){
 if(hasPanelWork()&&!confirm(t().resetConfirm))return;
 if(!hasPanelWork()&&($('topic').value.trim()||$('context').value.trim())&&!confirm(t().replaceContextConfirm))return;
 clearPanel(false);fillExample();await generatePanel(true);
 if(state.questions[0]){$('answer').value=(examples[lang()]||examples.en).answer;saveCurrentAnswer();updateCounts();$('answerCard').scrollIntoView({behavior:'smooth',block:'center'})}
}

async function generatePanel(fromDemo=false){
 const topic=$('topic').value.trim();if(!topic){$('generateError').textContent=t().topicRequired;$('topic').focus();return}
 if(hasPanelWork()&&!fromDemo&&!confirm(t().resetConfirm))return;
 $('generateError').textContent='';$('generateNotice').classList.add('hidden');$('generateBtn').disabled=true;$('generateBtn').textContent=t().building;
 try{
  const data=await postJSON('/api/questions',{topic,abstract:$('context').value.trim(),language:lang()});
  state.questions=data.questions||[];state.currentIndex=0;state.records={};$('answer').value='';
  $('questionsCard').classList.remove('hidden');$('answerCard').classList.remove('hidden');$('resultCard').classList.add('hidden');$('sessionComplete').classList.add('hidden');
  renderQuestions();renderSelected();updateProgress();persistRaw();
  if(data.notice){$('generateNotice').textContent=data.notice;$('generateNotice').classList.remove('hidden')}
  if(!fromDemo)$('questionsCard').scrollIntoView({behavior:'smooth',block:'start'});
 }catch(err){$('generateError').textContent=err.message||t().requestFailed}
 finally{$('generateBtn').disabled=false;$('generateBtn').textContent=t().buildPanel}
}

function renderQuestions(){
 if(!state.questions.length){$('questionList').innerHTML='';return}
 $('questionList').innerHTML=state.questions.map((item,index)=>{const rec=state.records[item.id]||{},done=!!rec.result;return `<button type="button" class="question-card ${index===state.currentIndex?'active':''} ${done?'done':''}" data-index="${index}" aria-pressed="${index===state.currentIndex}"><span class="avatar">${index+1}</span><span><span class="q-role">${escapeHtml(item.role||'Examiner')}</span><span class="q-text">${escapeHtml(item.question||'')}</span><span class="q-category">${escapeHtml(item.category||'')}</span></span><span class="done-mark">${done?'✓':''}</span></button>`}).join('');
 document.querySelectorAll('.question-card').forEach(btn=>btn.addEventListener('click',()=>selectQuestion(Number(btn.dataset.index))));
}
function selectQuestion(index){
 if(!state.questions[index])return;saveCurrentAnswer();state.currentIndex=index;
 const item=state.questions[index],rec=state.records[item.id]||{};$('answer').value=rec.answer||'';$('evaluateError').textContent='';$('voiceStatus').textContent='';
 renderQuestions();renderSelected();updateCounts();if(rec.result){showResult(rec.result);$('resultCard').classList.remove('hidden')}else{$('resultCard').classList.add('hidden')}
 persistRaw();$('answerCard').scrollIntoView({behavior:'smooth',block:'center'});
}
function renderSelected(){const item=state.questions[state.currentIndex];if(!item)return;$('selectedAvatar').textContent=state.currentIndex+1;$('selectedRole').textContent=item.role||'';$('selectedQuestion').textContent=item.question||''}
function renderExistingResult(){const item=state.questions[state.currentIndex],result=item&&state.records[item.id]?.result;if(result){showResult(result);$('resultCard').classList.remove('hidden')}}

async function evaluateAnswer(){
 const item=state.questions[state.currentIndex],answer=$('answer').value.trim();if(!item)return;
 if(!answer){$('evaluateError').textContent=t().answerRequired;$('answer').focus();return}
 $('evaluateError').textContent='';$('evaluateBtn').disabled=true;$('evaluateBtn').textContent=t().evaluating;
 try{
  const data=await postJSON('/api/evaluate',{topic:$('topic').value.trim(),abstract:$('context').value.trim(),question:item.question,answer,language:lang()});
  state.records[item.id]={answer,result:data};showResult(data);renderQuestions();updateProgress();persistRaw();$('resultCard').classList.remove('hidden');$('resultCard').scrollIntoView({behavior:'smooth',block:'start'});
 }catch(err){$('evaluateError').textContent=err.message||t().requestFailed}
 finally{$('evaluateBtn').disabled=false;$('evaluateBtn').textContent=t().evaluate}
}
function ratingFor(score){if(score<60)return t().ratingNeeds;if(score<75)return t().ratingDeveloping;if(score<90)return t().ratingStrong;return t().ratingExcellent}
function showResult(data){
 $('score').textContent=data.score;$('scoreRing').style.setProperty('--score',data.score);$('rating').textContent=ratingFor(Number(data.score||0));
 const keys=['clarity','relevance','evidence','structure'];$('breakdown').innerHTML=keys.map(key=>{const value=Number(data.dimensions?.[key]||0);return `<div class="metric-row"><span>${escapeHtml(t()[key])}</span><div class="bar"><span style="width:${value}%"></span></div><b>${value}</b></div>`}).join('');
 $('strengths').innerHTML=(data.strengths||[]).map(x=>`<li>${escapeHtml(x)}</li>`).join('');$('improvements').innerHTML=(data.improvements||[]).map(x=>`<li>${escapeHtml(x)}</li>`).join('');$('feedback').textContent=data.feedback||'';$('frameworkText').textContent=data.improved_answer||'';$('nextTip').textContent=data.next_tip||'';
 $('scoreExplanation').textContent=data.mode==='llm'?t().aboutScoreLive:t().aboutScoreDemo;if(data.notice){$('resultNotice').textContent=data.notice;$('resultNotice').classList.remove('hidden')}else{$('resultNotice').classList.add('hidden')}
}

function updateProgress(){
 const done=state.questions.filter(q=>state.records[q.id]?.result).length,total=state.questions.length||5,percent=Math.round(done/total*100);$('progressBar').style.width=`${percent}%`;$('topProgressBar').style.width=`${percent}%`;
 $('progressText').textContent=`${done} ${t().of} ${total} ${t().practised}`;$('topProgressText').textContent=$('progressText').textContent;$('progressPercent').textContent=`${percent}%`;
 const entries=state.questions.map(q=>state.records[q.id]?.result).filter(Boolean);if(!entries.length){$('averageScore').textContent='—';$('focusArea').textContent='—';$('sessionComplete').classList.add('hidden');return}
 $('averageScore').textContent=Math.round(entries.reduce((sum,r)=>sum+Number(r.score||0),0)/entries.length);const totals={clarity:0,relevance:0,evidence:0,structure:0};entries.forEach(r=>Object.keys(totals).forEach(k=>totals[k]+=Number(r.dimensions?.[k]||0)));const weakest=Object.keys(totals).sort((a,b)=>totals[a]-totals[b])[0];$('focusArea').textContent=t()[weakest];
 $('sessionComplete').classList.toggle('hidden',!(done===total&&state.questions.length));
}
function weakestQuestionIndex(){let best={index:0,value:Infinity};state.questions.forEach((q,index)=>{const r=state.records[q.id]?.result;if(!r)return;const values=Object.values(r.dimensions||{});const avg=values.length?values.reduce((a,b)=>a+Number(b||0),0)/values.length:Infinity;if(avg<best.value)best={index,value:avg}});return best.index}
function nextQuestion(){if(!state.questions.length)return;let target=state.questions.findIndex((q,i)=>i!==state.currentIndex&&!state.records[q.id]?.result);if(target<0)target=(state.currentIndex+1)%state.questions.length;selectQuestion(target)}
function retakeWeakest(){selectQuestion(weakestQuestionIndex());$('answer').focus()}
function resetSession(){if(hasSessionWork()&&!confirm(t().resetConfirm))return;clearPanel(true);sessionStorage.removeItem('fdc-v22');$('researchCard').scrollIntoView({behavior:'smooth'})}

async function uploadResearch(file){
 if(!file)return;if(file.size>6*1024*1024){$('fileStatus').textContent=`${t().requestFailed} ${t().uploadSub}`;return}
 if(hasPanelWork()&&!confirm(t().resetConfirm)){$('fileInput').value='';return}if(hasPanelWork())clearPanel(false);
 if($('context').value.trim()&&!confirm(t().replaceContextConfirm)){$('fileInput').value='';return}
 $('fileStatus').textContent='…';const form=new FormData();form.append('file',file);
 try{
  const response=await fetch('/api/extract',{method:'POST',body:form});let data={};try{data=await response.json()}catch(_){ }
  if(!response.ok){if(response.status===413||response.status===415)$('fileStatus').textContent=t().uploadSub;else $('fileStatus').textContent=t().requestFailed;return}
  $('context').value=data.text||'';if(!$('topic').value.trim()&&data.suggested_topic)$('topic').value=data.suggested_topic;$('fileName').textContent=data.filename||file.name;$('fileStatus').textContent=`${t().fileLoaded} ${data.filename}.${data.truncated?' '+t().fileTruncated:''}`;updateCounts();persistRaw();
 }catch(_){$('fileStatus').textContent=navigator.onLine?t().requestFailed:t().offlineError}finally{$('fileInput').value=''}
}

function hearQuestion(){const item=state.questions[state.currentIndex];if(!item||!('speechSynthesis'in window)){$('voiceStatus').textContent=t().voiceUnavailable;return}speechSynthesis.cancel();const utterance=new SpeechSynthesisUtterance(item.question);utterance.lang=speechLanguages[lang()]||'en-US';utterance.rate=.96;speechSynthesis.speak(utterance);$('voiceStatus').textContent=t().hearing}
function setupVoice(){
 const Recognition=window.SpeechRecognition||window.webkitSpeechRecognition;if(!Recognition){recognition=null;$('dictateBtn').disabled=true;$('dictateBtn').title=t().voiceUnavailable;return}
 $('dictateBtn').disabled=false;$('dictateBtn').title='';recognition=new Recognition();recognition.interimResults=false;recognition.continuous=false;
 recognition.onstart=()=>{$('voiceStatus').textContent=t().listening;$('dictateBtn').disabled=true};recognition.onend=()=>{$('dictateBtn').disabled=false};recognition.onerror=()=>{$('voiceStatus').textContent=t().voiceUnavailable;$('dictateBtn').disabled=false};recognition.onresult=e=>{const text=Array.from(e.results).map(r=>r[0].transcript).join(' ').trim();$('answer').value=[$('answer').value.trim(),text].filter(Boolean).join(' ');updateCounts();saveCurrentAnswer()}
}
function startDictation(){if(!recognition){$('voiceStatus').textContent=t().voiceUnavailable;return}recognition.lang=speechLanguages[lang()]||'en-US';try{recognition.start()}catch(_){ }}
function updateCounts(){$('contextCount').textContent=$('context').value.length;$('answerCount').textContent=wordsCount($('answer').value);saveCurrentAnswer(false);persistRaw()}
function updateMode(){const live=state.health?.mode==='llm';$('engineBadge').textContent=live?t().liveAI:t().demoSimulation;$('engineBadge').classList.toggle('mode-live',live);$('engineBadge').classList.toggle('mode-demo',!live)}
async function loadHealth(){try{const r=await fetch('/health',{cache:'no-store'});if(r.ok){state.health=await r.json();updateMode()}}catch(_){ }}
async function copyFramework(){const text=$('frameworkText').textContent;try{if(navigator.clipboard)await navigator.clipboard.writeText(text);else{const ta=document.createElement('textarea');ta.value=text;document.body.appendChild(ta);ta.select();document.execCommand('copy');ta.remove()}$('copyStatus').textContent=t().copied}catch(_){$('copyStatus').textContent=t().requestFailed}}
function handleLanguageChange(){const next=lang();if(next===state.lastLanguage)return;if(hasPanelWork()&&!confirm(trFor(state.lastLanguage).languageChangeConfirm)){$('language').value=state.lastLanguage;return}if(hasPanelWork())clearPanel(false);state.lastLanguage=next;applyLanguage();persistRaw();setupVoice()}
function protectResearchEdit(event){if(!hasPanelWork())return;if(confirm(t().resetConfirm)){clearPanel(false)}else{event.target.blur()}}
function restoreVisibleState(){if(!state.questions.length)return;$('questionsCard').classList.remove('hidden');$('answerCard').classList.remove('hidden');renderQuestions();renderSelected();const item=state.questions[state.currentIndex];$('answer').value=state.records[item?.id]?.answer||'';renderExistingResult();updateCounts();updateProgress()}

$('language').addEventListener('change',handleLanguageChange);$('guidedDemoBtn').addEventListener('click',guidedDemo);$('ownBtn').addEventListener('click',()=>$('researchCard').scrollIntoView({behavior:'smooth'}));$('exampleBtn').addEventListener('click',useExample);$('generateBtn').addEventListener('click',()=>generatePanel(false));$('fileInput').addEventListener('change',e=>uploadResearch(e.target.files?.[0]));$('dropzone').addEventListener('click',e=>{if(e.target.id!=='fileInput')$('fileInput').click()});$('dropzone').addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();$('fileInput').click()}});['dragenter','dragover'].forEach(ev=>$('dropzone').addEventListener(ev,e=>{e.preventDefault();$('dropzone').classList.add('dragover')}));['dragleave','drop'].forEach(ev=>$('dropzone').addEventListener(ev,e=>{e.preventDefault();$('dropzone').classList.remove('dragover')}));$('dropzone').addEventListener('drop',e=>uploadResearch(e.dataTransfer.files?.[0]));$('sampleAnswerBtn').addEventListener('click',()=>{$('answer').value=(examples[lang()]||examples.en).answer;updateCounts();saveCurrentAnswer()});$('hearBtn').addEventListener('click',hearQuestion);$('dictateBtn').addEventListener('click',startDictation);$('evaluateBtn').addEventListener('click',evaluateAnswer);$('copyBtn').addEventListener('click',copyFramework);$('nextBtn').addEventListener('click',nextQuestion);$('resetBtn').addEventListener('click',resetSession);$('retakeBtn').addEventListener('click',retakeWeakest);$('topic').addEventListener('focus',protectResearchEdit);$('context').addEventListener('focus',protectResearchEdit);$('topic').addEventListener('input',persistRaw);$('context').addEventListener('input',updateCounts);$('answer').addEventListener('input',updateCounts);

restore();applyLanguage();restoreVisibleState();updateCounts();updateProgress();setupVoice();loadHealth();