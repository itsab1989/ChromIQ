/* ArgyllCMS 3.5.0 alphix, driven from the command line (tests only).
 *
 * Compiled by tests/test_pattern_variants_read_by_both_readers.py against
 * native/instlib/alphix.c (identical to Argyll's target/alphix.c) with the
 * numsup.h stub beside this file, so the suite asks ArgyllCMS's OWN code:
 *   harness a <pattern>                 -> CMCT n, then i|label|nix per index
 *   harness o <strip> <patch> <ixord>   -> loc|patch_location_order per stdin line
 * patch_location_order is what chartread (spectro/chartread.c) and
 * chromiq-chartread call on every SAMPLE_LOC before they sort and read.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "alphix.h"
int main(int argc, char **argv) {
  /* mode a: pattern -> cmct and labels; mode o: spat ppat ixord loc... -> order */
  if (argv[1][0]=='a') {
    alphix *p = new_alphix(argv[2]); int n = p->maxlen(p); printf("CMCT %d\n", n);
    for (int i=0;i<n;i++){ char *s=p->aix(p,i); printf("%d|%s|%d\n", i, s?s:"(NULL)", s?p->nix(p,s):-9); free(s);} 
  } else {
    alphix *s = new_alphix(argv[2]), *pp = new_alphix(argv[3]); int ix = atoi(argv[4]);
    char line[256]; while (fgets(line,256,stdin)) { line[strcspn(line,"\n")]=0; printf("%s|%d\n", line, patch_location_order(s,pp,ix,line)); }
  }
  return 0;
}
