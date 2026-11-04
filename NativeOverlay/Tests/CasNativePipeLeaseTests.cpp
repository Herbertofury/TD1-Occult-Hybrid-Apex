#include "../Source/ApexCasNativePipeWin.h"
#include <stdexcept>
static void Check(bool value) {if(!value)throw std::runtime_error("Native local lease regression");}
int main() {
    td1::nativecas::pipe::Mailbox box;
    box.generation=7;box.scope="exact-scope";box.stop=false;
    // UI metadata is local, including while Source's TCP connection is opening.
    Check(!box.connected && box.MatchesOpened(7,"exact-scope") && !box.Matches(7,"exact-scope"));
    Check(!box.MatchesOpened(6,"exact-scope") && !box.MatchesOpened(7,"another-scope"));
    Check(box.Poll(7,"exact-scope")=="WAIT");
    box.connected=true;Check(box.Matches(7,"exact-scope"));
    Check(box.Close(7,"exact-scope")=="CLOSED");
    Check(!box.MatchesOpened(7,"exact-scope") && !box.Matches(7,"exact-scope"));
    Check(box.Poll(7,"exact-scope")=="CLOSED");
}
