// Shared UI routing only. Native editable fields keep their own undo stack.
export function historyShortcut(event){
 if(event.defaultPrevented||event.repeat||event.altKey||Boolean(event.ctrlKey)===Boolean(event.metaKey))return null;
 const target=event.target,tag=String(target?.tagName??'').toLowerCase(),type=String(target?.type??'').toLowerCase();
 if(target?.isContentEditable||tag==='textarea'||(tag==='input'&&!['range','checkbox','radio','button','submit','reset'].includes(type)))return null;
 const key=String(event.key??'').toLowerCase();
 if(key==='z')return event.shiftKey?'redo':'undo';
 if(key==='y'&&!event.shiftKey)return 'redo';
 return null;
}
export function routeHistoryShortcut(event,buttons){
 const action=historyShortcut(event),button=action&&buttons[action];
 if(!button||button.disabled)return false;
 event.preventDefault();button.click();return true;
}
