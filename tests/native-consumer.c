#include <assert.h>
#include "native-answer.h"
int main(void) {
  for (uint32_t value=0; value<100; value++) assert(native_answer(value)==value+EXPECTED);
  assert(native_answer(UINT32_MAX)==EXPECTED-1);
  return 0;
}
