use v6.d;
my $data = Rakudo::Internals::JSON.from-json(@*ARGS[0].IO.slurp);
my @records = ($data ~~ Associative ?? $data<distributions> !! $data).list;
for @records -> %record {
    my %meta = %record<meta>;
    for %meta<provides>.keys.sort -> $module {
        my $spec = CompUnit::DependencySpecification.new(
            :short-name($module),
            :version-matcher(Version.new(~(%meta<version> // %meta<ver> // '0'))),
            :auth-matcher(~(%meta<auth> // '')),
            :api-matcher(Version.new(~(%meta<api> // '0')))
        );
        my $unit = $*REPO.need($spec);
        die "Failed to compile captured module $module" unless $unit.defined;
    }
}
