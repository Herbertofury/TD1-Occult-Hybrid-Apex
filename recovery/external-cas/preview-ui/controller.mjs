// Coalesces replaceable preview requests only. Never use for edit/write commands.
export class PreviewController {
  constructor(render, display, status, idle = null) { this.idle=idle; this.render=render;this.display=display;this.status=status;this.epoch=0;this.sequence=0;this.latest=null;this.running=false;this.opened=false; }
  notify(message) { try { this.status(message); } catch(error) { this.observerError=error; } }
  open() { this.epoch++;this.opened=true;this.latest=null; }
  close() { this.epoch++;this.opened=false;this.latest=null;this.notify('Closed'); }
  request(parameters) {
    if(!this.opened) return;
    this.latest={...parameters,epoch:this.epoch,sequence:++this.sequence};
    this.notify('Rendering; previous frame is stale');this.pump();
  }
  async pump() {
    if(this.running||!this.opened||!this.latest) return;
    const request=this.latest;this.running=true;
    try {
      const frame=await this.render(request);
      if(this.opened&&this.latest===request&&this.epoch===request.epoch) {
        this.display(frame,request);this.notify('Current frame '+request.sequence);
      }
    } catch(error) {
      if(this.opened&&this.latest===request&&this.epoch===request.epoch) this.notify('Failed; last-good frame retained: '+error.message);
    } finally {
      this.running=false;
      if(this.opened&&this.latest!==request) this.pump();
      else if(this.opened&&this.latest===request&&this.idle){try{this.idle(request);}catch(error){this.observerError=error;}}
    }
  }
}
