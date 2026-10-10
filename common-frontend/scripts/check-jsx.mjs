import ts from 'typescript';
import { readdirSync, readFileSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';
const root=resolve(import.meta.dirname,'..');
function files(dir){return readdirSync(dir,{withFileTypes:true}).flatMap(entry=>entry.isDirectory()?files(resolve(dir,entry.name)):entry.name.endsWith('.tsx')?[resolve(dir,entry.name)]:[]);}
let total=0;
for(const path of [resolve(root,'App.tsx'),...files(resolve(root,'src'))]){
  const source=readFileSync(path,'utf8'),tree=ts.createSourceFile(path,source,ts.ScriptTarget.Latest,true,ts.ScriptKind.TSX),edits=[];
  function visit(node){
    if(ts.isJsxText(node)&&ts.isJsxElement(node.parent)){
      const tag=node.parent.openingElement.tagName.getText(tree),text=node.getText(tree);
      if(['View','Card','ScrollView','Pressable'].includes(tag)&&text.length&&(!/\r|\n/.test(text)||text.trim()))edits.push({start:node.pos,end:node.end,text});
    }
    ts.forEachChild(node,visit);
  }
  visit(tree);total+=edits.length;
  if(edits.length&&process.argv.includes('--fix')){let fixed=source;for(const edit of edits.reverse()){if(edit.text.trim())throw new Error(`Non-whitespace text under a native view in ${path}`);fixed=fixed.slice(0,edit.start)+fixed.slice(edit.end);}writeFileSync(path,fixed);}
  else for(const edit of edits)console.log(`${path}:${tree.getLineAndCharacterOfPosition(edit.start).line+1}: bare text ${JSON.stringify(edit.text)}`);
}
if(total&&!process.argv.includes('--fix'))process.exitCode=1;
console.log(`${total} bare text nodes ${process.argv.includes('--fix')?'fixed':'found'}.`);
