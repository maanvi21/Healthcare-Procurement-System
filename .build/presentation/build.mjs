import fs from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";

const workspace = process.cwd();
const skill = "C:/Users/maanv/.codex/plugins/cache/openai-primary-runtime/presentations/26.1025.11240/skills/presentations";
const work = path.join(workspace, ".build", "presentation");
const rendered = path.join(work, "rendered");
const draft = path.join(work, "draft.pptx");
const finalFile = path.join(workspace, "docs", "MediSource_AI_Project_Overview.pptx");
await fs.mkdir(rendered, { recursive: true });
const artifactTool = await import(pathToFileURL("C:/Users/maanv/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/@oai/artifact-tool/dist/artifact_tool.mjs").href);
const { Presentation, PresentationFile } = artifactTool;
const P = Presentation.create({ slideSize: { width: 1280, height: 720 } });
const K = { navy:"#102A43", blue:"#2563A6", teal:"#087E78", paper:"#F5F8FC", white:"#FFFFFF", ink:"#17324D", muted:"#526B80", line:"#C6D4E0", pale:"#EAF2FB", aqua:"#E8F5F3", amber:"#A45B08", paleAmber:"#FFF4E3", red:"#A23535", paleRed:"#FCEEEE", green:"#23734D", paleGreen:"#EAF5EE" };
const FONT = "Arial";
function txt(s,t,x,y,w,h,z=20,c=K.ink,b=false,a="left"){
  const q=s.shapes.add({geometry:"textbox",position:{left:x,top:y,width:w,height:h},fill:"none",line:{style:"solid",fill:"none",width:0}});
  q.text=t; q.text.style={typeface:FONT,fontSize:z,color:c,bold:b,alignment:a,verticalAlignment:"middle"}; return q;
}
function box(s,x,y,w,h,fill=K.white,stroke=K.line){
  return s.shapes.add({geometry:"roundRect",position:{left:x,top:y,width:w,height:h},fill,line:{style:"solid",fill:stroke,width:1}});
}
function slide(title,sub){
  const s=P.slides.add(); s.background.fill=K.paper;
  txt(s,title,64,40,1150,60,36,K.navy,true);
  if(sub)txt(s,sub,66,103,1140,38,17,K.muted);
  return s;
}
function card(s,x,y,w,h,title,body,accent=K.teal){
  box(s,x,y,w,h); box(s,x,y,8,h,accent,accent);
  txt(s,title,x+22,y+14,w-42,31,21,K.navy,true);
  txt(s,body,x+22,y+53,w-42,h-64,16,K.muted);
}

// Cover
{
 const s=P.slides.add(); s.background.fill=K.navy;
 box(s,835,0,445,720,"#173F5F","#173F5F");
 ["DOCUMENTS","APPROVALS","CONTRACTS + E-SIGN"].forEach((t,i)=>{box(s,890,145+i*165,325,125,"#1A5570","#1A5570");txt(s,t,905,185+i*165,295,42,20,K.white,true,"center");});
 txt(s,"MediSource AI",78,190,700,86,58,K.white,true);
 txt(s,"Healthcare procurement operations",82,290,690,50,28,"#CDE5F5");
 txt(s,"One control panel for documents, suppliers, approvals, inventory, risk, notifications, and electronic signatures.",84,382,650,125,21,K.white);
 txt(s,"Project overview · Architecture · Implemented capabilities",84,594,680,32,16,"#B5CCDD");
}
// Problem and solution
{
 const s=slide("Procurement work needs one visible record","MediSource AI connects records and decisions that span separate tools.");
 card(s,72,185,520,390,"The operating problem","Supplier documents arrive in different formats.\n\nReviewers need to verify extracted details and risk flags.\n\nApprovals, supplier contacts, contract signatures, and inventory status can be hard to follow across disconnected systems.",K.amber);
 card(s,690,185,520,390,"The platform response","A shared control panel exposes document status, OCR text and fields, approval history, notifications, contract status, and signed files.\n\nEvents coordinate service-owned workflows while PostgreSQL and MinIO keep records and artifacts.",K.teal);
 txt(s,"DESIGN GOAL",76,615,140,25,14,K.blue,true);txt(s,"Make exceptions actionable and completion verifiable.",224,606,900,40,23,K.navy,true);
}
// Architecture
{
 const s=slide("Service architecture with a shared event backbone","FastAPI services own their domains; Kafka carries workflow events between them.");
 box(s,65,190,220,90,K.pale,"#85A9C6");txt(s,"React CPanel",78,207,195,28,21,K.navy,true,"center");txt(s,"same-origin UI",78,241,195,22,14,K.muted,false,"center");
 box(s,335,190,220,90,K.pale,"#85A9C6");txt(s,"Nginx gateway",348,207,195,28,21,K.navy,true,"center");txt(s,"/api routing",348,241,195,22,14,K.muted,false,"center");txt(s,"→",285,212,50,35,30,K.blue,true,"center");
 box(s,605,165,610,270,K.aqua,"#74B7A6");txt(s,"FastAPI domain services",625,178,570,32,22,K.navy,true,"center");
 const names=[["Documents","OCR · fields · fraud"],["Vendors","onboarding · compliance"],["Approvals","OPA · Temporal"],["Inventory","reservation · backorder"],["Contracts","PDF · OpenSign"],["Risk + notifications","MLflow · adapters"]];
 names.forEach((r,i)=>{const x=628+(i%3)*188,y=230+Math.floor(i/3)*85;box(s,x,y,170,66);txt(s,r[0],x+7,y+7,156,23,16,K.navy,true,"center");txt(s,r[1],x+7,y+34,156,20,12,K.muted,false,"center");});
 const blocks=[["Kafka","domain events"],["Data","PostgreSQL · MinIO · Redis"],["External","OpenSign · email/SMS/chat · Groq"]];
 blocks.forEach((r,i)=>{const x=65+i*390;box(s,x,495,350,100,i===0?K.pale:i===1?"#F0EDFC":K.paleAmber);txt(s,r[0],x+15,510,320,28,22,K.navy,true,"center");txt(s,r[1],x+15,550,320,23,14,K.muted,false,"center");});
 txt(s,"Separate service databases · OPA policies · Temporal approval state · MLflow model tracking",78,625,1110,30,17,K.muted);
}
// Business workflow summary
{
 const s=slide("From supplier document to signed contract","A linear view of the process; errors and review states remain visible at each stage.");
 const rows=[["01  Ingest","Upload or watched Input folder"],["02  Extract","OCR text · fields · confidence · fraud checks"],["03  Review","Correct values or route to approvers"],["04  Approve","OPA routing · Temporal decision history"],["05  Sign","PDF to OpenSign · verified completion returns signed PDF"]];
 rows.forEach((r,i)=>{const y=175+i*71;txt(s,r[0],90,y,260,34,22,K.navy,true);txt(s,r[1],390,y,795,34,18,K.muted);if(i<rows.length-1)txt(s,"↓",175,y+36,38,28,18,K.blue,true,"center");});
 box(s,75,565,1135,78,K.paleRed,"#DCA2A2");txt(s,"Failure paths",94,578,170,28,18,K.red,true);
 txt(s,"Low confidence → review · Worker error → Failed + reason + retry · Provider issue → draft + error · Decline → declined · Only verified completion exposes a signed artifact",260,576,920,49,15,K.ink);
}
// Documents
{
 const s=slide("Document intelligence shows its evidence","Reviewers can inspect extracted values and the OCR text used to derive them.");
 card(s,70,180,500,410,"Visible for every document","Processing state and exception reason\nDocument type and overall confidence\nExtracted fields with individual confidence\nExpandable OCR source text\nFraud signals and missing required values\nManual corrections retained for audit",K.teal);
 box(s,650,180,555,410);txt(s,"REVIEW RECORD",680,205,470,25,14,K.blue,true);txt(s,"Supplier invoice",680,244,470,40,26,K.navy,true);
 const rs=[["Vendor","Northstar Medical Supplies","92%"],["Invoice number","NS-10492","98%"],["Invoice date","14 Oct 2026","96%"],["Total amount","INR 41,300","89%"]];
 rs.forEach((r,i)=>{const y=310+i*54;txt(s,r[0],680,y,150,23,15,K.muted,true);txt(s,r[1],835,y,245,23,15,K.ink);txt(s,r[2],1090,y,74,23,14,i===3?K.amber:K.green,true,"right");});
 txt(s,"Illustrative review fields; values shown are examples, not live application records.",680,540,470,28,13,K.muted);
}
// Approval + operational services
{
 const s=slide("Approvals combine policy, people, and operational context","The CPanel presents the status; domain services keep decision history.");
 card(s,70,185,355,365,"Approval routing","OPA evaluates policy inputs and selects the approver chain.\n\nTemporal waits for decisions, records outcomes, and escalates timed-out steps.\n\nApproval requests can notify the configured role mailbox.",K.blue);
 card(s,462,185,355,365,"Vendor and risk","Profiles retain contact and compliance data.\n\nRisk scoring combines supplier, spend, fraud, and operational observations.\n\nAnomalies include review reasons; cold-start scores are identified as estimates.",K.teal);
 card(s,854,185,355,365,"Inventory and alerts","Stock reservations use item, batch, and expiry.\n\nRedis locks protect concurrent reservations. Shortfalls surface as backorders.\n\nNotifications show sent, simulated, or failed delivery state.",K.amber);
 txt(s,"Live email and messaging delivery requires credentials for the selected provider.",78,600,1110,32,18,K.navy,true);
}
// E-sign
{
 const s=slide("Digital signing has a provider-backed lifecycle","Contract generation and signing status are visible in the contract repository.");
 const xs=[75,475,875], fills=[K.pale,K.paleAmber,K.paleGreen], strokes=["#85A9C6","#D2A55C","#8BB89A"];
 const titles=["Contract PDF","OpenSign request","Signed archive"], details=["Approved procurement data\nTerms and renewal dates\nDedicated signature page","Email + signature widget\nEnvelope ID and signer link\nPending or declined state","Verified completion callback\nSigned PDF + certificate in MinIO\nCPanel download link"];
 xs.forEach((x,i)=>{box(s,x,190,330,340,fills[i],strokes[i]);txt(s,titles[i].toUpperCase(),x+20,220,290,28,14,i===2?K.green:K.blue,true,"center");txt(s,details[i],x+30,300,270,150,19,K.navy,false,"center");});
 txt(s,"Unavailable provider leaves the contract in draft with an error. Demo envelopes are labelled and are never marked signed.",88,580,1100,60,16,K.ink);
}
// Status and deployment
{
 const s=slide("Implementation status and deployment needs","Code-level checks pass; provider and cluster checks require the target environment.");
 card(s,70,180,535,365,"Verified in this workspace","Frontend production build: passed\nPython source compilation: passed\nDiff validation: passed\n\nDocument failure/retry states, editable notification templates, PDF signing requests, webhook verification, and signed-artifact links are implemented.",K.green);
 card(s,670,180,535,365,"Requires live configuration","Docker runtime unavailable in this workspace; containers were not started.\n\nOpenSign requires API token, webhook secret, public callback, and artifact-host allowlist.\n\nEmail/SMS/chat require credentials. Kubernetes watched folders require RWX storage.",K.amber);
 txt(s,"Before a production demonstration",80,600,290,30,18,K.blue,true);
 txt(s,"Run database migrations and full integration checks in the target cluster with provider credentials.",370,594,800,42,18,K.navy,true);
}

for(let i=0;i<P.slides.items.length;i++){
 const png=await P.export({slide:P.slides.items[i],format:"png",scale:1});
 await fs.writeFile(path.join(rendered,"slide-"+String(i+1).padStart(2,"0")+".png"),new Uint8Array(await png.arrayBuffer()));
}
const pptx=await PresentationFile.exportPptx(P); await pptx.save(draft);
const {finalizePresentation}=await import(pathToFileURL(path.join(skill,"container_tools/artifact_tool_utils.mjs")).href);
const result=await finalizePresentation({
 workspaceDir:workspace,candidatePath:draft,finalPath:finalFile,
 pythonExecutable:"C:/Users/maanv/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe",
 integrityValidatorPath:path.join(skill,"container_tools/inspect_presentation_package_integrity.py"),
 layoutValidatorPath:path.join(skill,"container_tools/inspect_presentation_layout_geometry.py"),
 layoutArgs:["--expected-slide-size-emu","12192000,6858000","--validate-heading-fit"],
 receiptPath:path.join(work,"validation.json"),fontPolicy:{basis:"design",families:[FONT]},verifyArtifactToolImport:true
});
console.log(JSON.stringify(result));
