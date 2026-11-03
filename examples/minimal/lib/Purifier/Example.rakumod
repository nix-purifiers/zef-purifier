unit module Purifier::Example;
use JSON::Marshal;
sub serialized() is export { marshal({answer => 42}, :!pretty) }
