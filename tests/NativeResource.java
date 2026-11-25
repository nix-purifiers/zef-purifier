import java.lang.foreign.*;
import static java.lang.foreign.ValueLayout.JAVA_INT;
class NativeResource {
  public static void main(String[] args) throws Throwable {
    System.loadLibrary("native-answer");
    var function = Linker.nativeLinker().downcallHandle(
      SymbolLookup.loaderLookup().find("native_answer").orElseThrow(),
      FunctionDescriptor.of(JAVA_INT, JAVA_INT));
    int expected = Integer.parseInt(args[0]);
    for (int i=0; i<100; i++)
      if ((int)function.invokeExact(i) != i+expected) throw new AssertionError();
    if ((int)function.invokeExact(-1) != expected-1) throw new AssertionError();
    System.out.println("Actual Zef Java library-path projection FFM100/overflow PASS");
  }
}
