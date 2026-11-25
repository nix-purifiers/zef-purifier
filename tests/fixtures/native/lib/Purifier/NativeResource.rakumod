unit module Purifier::NativeResource;
use NativeCall;
sub native-answer(uint32 --> uint32) is native(%?RESOURCES<libraries/native-answer>) is symbol('native_answer') { * }
our sub answer(Int $input --> Int) is export { native-answer($input) }
