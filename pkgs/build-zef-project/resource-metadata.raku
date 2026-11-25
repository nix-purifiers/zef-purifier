use Zef;
my $root = @*ARGS[0].IO.absolute.IO;
my $distribution = Distribution::Path.new($root);
say Zef::to-json($distribution.meta.hash);
