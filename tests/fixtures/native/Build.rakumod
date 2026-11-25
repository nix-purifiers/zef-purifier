unit class Build;
method build($workdir) {
    my $root = $workdir.IO;
    my $directory = $root.add('resources/libraries');
    $directory.mkdir(:parents);
    $root.add('resources/include').mkdir(:parents);
    $root.add('native/native-answer.h').copy($root.add('resources/include/native-answer.h'));
    $root.add('resources/data').mkdir(:parents);
    $root.add('resources/data/message.txt').spurt('native resource preserved');
    my $process = run 'cc', '-shared', '-fPIC',
        $root.add('native/answer.c').Str, '-o',
        $directory.add($*VM.platform-library-name('native-answer'.IO)).Str;
    die 'Native C compilation failed' unless $process.exitcode == 0;
    True
}
