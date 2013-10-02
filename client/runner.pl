use strict;
use warnings 'all';

use Time::HiRes qw / time sleep /;
use Carp;

my $cmd = "/usr/bin/wget --timeout=8 -e robots=off -U \"Mozilla/5.0 (X11; Linux x86_64; rv:10.0) Gecko/20100101 Firefox/10.0\" --page-requisites --no-check-certificate ";

my $uOfIResolver = "130.126.2.131";

sub run {
    (@_ == 1) || die;
    my ($website) = @_;
    my $start = time;
    system(join($cmd,$website," &>/dev/null"))
        || die "Failed to download website";
    my $end = time;
    return $end-$start;
}

sub setResolver {
    (@_ == 1) || die;
    my ($newResolver) = @_;
    system("sudo echo \"nameserver ".$newResolver." \" > /etc/resolv.conf")
        || die "Failed to set resolver";
}

sub main {
    (@_ == 1) || die;
    my ($domainListFile) = @_;
    -e $domainListFile || die "file ".$domainListFile." not found";
    open DOMAINFILE,">",$domainListFile || die "failed to open file for read";
    for(my $i = 0; $i<100; $i++) {
        open DATAFILE,"<","result_wor_".$i.".txt"
            || die "failed to open file for write";
        setResolver($uOfIResolver);
        while(<DOMAINFILE>) {
            my $thisDomain = $_;
            $thisDomain =~ s/\s*//g;
            my $runTime = run($thisDomain);
            my $lineToWrite = sprintf("%s,%d\n",$thisDomain,$runTime);
            print DATAFILE $lineToWrite;
            sleep(0.5)
        }
        close DATAFILE;

        seek DOMAINFILE,0,0;

        open DATAFILE,"<","result_wr_".$i.".txt"
            || die "failed to open file for write";
        setResolver("127.0.0.1");
        while(<DOMAINFILE>) {
            my $thisDomain = $_;
            $thisDomain =~ s/\s*//g;
            my $runTime = run($thisDomain);
            my $lineToWrite = sprintf("%s,%d\n",$thisDomain,$runTime);
            print DATAFILE $lineToWrite;
            sleep(0.5)
        }
        close DATAFILE;
        close DOMAINFILE;
    }
}

@ARGV == 1 || die;
main($ARGV[0]);
