import path from "node:path";
import { pathToFileURL } from "node:url";
const skill="C:/Users/maanv/.codex/plugins/cache/openai-primary-runtime/presentations/26.1025.11240/skills/presentations";
try {
 const {finalizePresentation}=await import(pathToFileURL(path.join(skill,"container_tools/artifact_tool_utils.mjs")).href);
 console.log("finalizer loaded");
 const result=await finalizePresentation({
  workspaceDir:process.cwd(),
  candidatePath:path.join(process.cwd(),".build","presentation","draft.pptx"),
  finalPath:path.join(process.cwd(),"docs","MediSource_AI_Project_Overview.pptx"),
  pythonExecutable:"C:/Users/maanv/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe",
  integrityValidatorPath:path.join(skill,"container_tools/inspect_presentation_package_integrity.py"),
  layoutValidatorPath:path.join(skill,"container_tools/inspect_presentation_layout_geometry.py"),
  layoutArgs:["--expected-slide-size-emu","12192000,6858000","--validate-heading-fit"],
  receiptPath:path.join(process.cwd(),".build","presentation","validation.json"),
  fontPolicy:{basis:"design",families:["Arial"]},
  verifyArtifactToolImport:false
 });
 console.log("FINALIZED",JSON.stringify(result));
} catch(e) { console.error("FINALIZE ERROR",e?.stack||e); process.exitCode=1; }
