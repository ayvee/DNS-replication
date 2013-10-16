use strict;
use warnings 'all';
use Data::Dumper;

my $domains = {};
my $outFileName = "output.csv";

foreach (@ARGV) {
    print "File is: ".$_."\n";
    open FILE, "<", $_ or die;
    while(<FILE>) {
        chomp;
        my $line = $_;
        my @tokens = split /,/, $line;
        (@tokens == 2) or die($line);
        my $domainName = $tokens[0];
        my $runtime = $tokens[1];
        if (defined $domains->{$domainName}) {
            push @{$domains->{$domainName}}, $runtime;
        } else {
            $domains->{$domainName} = [];
        }
    }
    close FILE;
}

open OUTPUT, ">", $outFileName or die;

foreach (keys %$domains) {
    my $thisDomain = $_;
    my $runtime = $domains->{$thisDomain};
    print OUTPUT $thisDomain.",";
    foreach (@$runtime) {
        print OUTPUT $_.",";
    }
    print OUTPUT "\n";
}
close OUTPUT;
