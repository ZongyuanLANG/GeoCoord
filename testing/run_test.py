#! /usr/bin/env python3

import subprocess
import glob
import filecmp
import os
import sys
import signal
import socket
import shutil
import tempfile
import atexit


def run_tests():
    print("|---------- running tests ----------|", file=log, flush=True)

    _, dirs, _ = os.walk(os.path.join(TSTDIR, "tests")).__next__()

    for test_dir in sorted(dirs, key=lambda x: x.split("_")[0]):
        if test_dir.startswith("."):
            continue

        with open(os.path.join(TSTDIR, "tests", test_dir, "info.txt")) as info_file:
            print(info_file.read(), flush=True)
            print(info_file.read(), file=log, flush=True)

        run_test(test_dir)


def run_test(test_dir):
    for data in sorted(glob.glob(os.path.join(TSTDIR, "tests", test_dir, "data*.sql"))):
        for queries in sorted(glob.glob(os.path.join(TSTDIR, "tests", test_dir, "queries*.sql"))):

            try:
                os.makedirs(os.path.join(TSTDIR, "results", test_dir.split("_")[1]))
            except FileExistsError:
                pass

            output = open(os.path.join(TSTDIR, "results", test_dir.split("_")[1], "{}-{}.log".format(data.split('/')[-1].split('.')[0], queries.split('/')[-1].split('.')[0])), "w")

            print("|---------- START TEST -- {}  -- {} -- {} ----------|".format(test_dir.split("_")[1], data.split('/')[-1].split('.')[0], queries.split('/')[-1].split('.')[0]), file=log, flush=True)

            print("---------- setting-up database", file=log, flush=True)
            subprocess.call(["createdb", DB], stdout=log, stderr=subprocess.STDOUT)  # this SHOULD never error

            print("---------- Loading GeoCoord Type", file=log, flush=True)
            proc = subprocess.Popen(["psql", DB, "-f", os.path.join(TSTDIR, "gcoord.sql")],
                                    bufsize=1, universal_newlines=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            stdout, stderr = proc.communicate()
            if "ERROR:" in stdout:
                print("Error: Postgres reported an error while executing {}".format(os.path.join(TSTDIR, "gcoord.sql")))
                print(stdout, flush=True)
                print(stdout, file=log, flush=True)
            if "CREATE TABLE" in stdout or "INSERT" in stdout or "DROP TYPE" in stdout:
                print("Error: Unexpected action done by {}".format(os.path.join(TSTDIR, "gcoord.sql")))
                print(stdout, flush=True)
                print(stdout, file=log, flush=True)
            if proc.wait() != 0:
                print("Error: Unexpected exit from {}".format(os.path.join(TSTDIR, "gcoord.sql")))
                print(stdout, flush=True)
                print(stdout, file=log, flush=True)
            print(stdout, file=log, flush=True)

            print("---------- Loading Test Schema", file=log, flush=True)
            proc = subprocess.Popen(["psql", DB, "-f", os.path.join(TSTDIR, "tests", test_dir, "schema.sql")],
                                    bufsize=1, universal_newlines=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            stdout, stderr = proc.communicate()
            if "ERROR:" in stdout:
                print("Error: Postgres reported an error while executing {}".format(os.path.join(TSTDIR, "tests", test_dir, "schema.sql")))
                print(stdout, flush=True)
                print(stdout, file=log, flush=True)
            if proc.wait() != 0:
                print("Error: Unexpected exit from {}".format(os.path.join(TSTDIR, "tests", test_dir, "schema.sql")))
                print(stdout, flush=True)
                print(stdout, file=log, flush=True)
            print(stdout, file=log, flush=True)

            print("---------- Loading Test Data", file=log, flush=True)
            proc = subprocess.Popen(["psql", DB, "-f", data],
                                    bufsize=1, universal_newlines=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            stdout, stderr = proc.communicate()
            if "ERROR:" in stdout:
                print("Error: Postgres reported an error while executing {}".format(data))
                print(stdout, flush=True)
                print(stdout, file=log, flush=True)
            if proc.wait() != 0:
                print("Error: Unexpected exit from {}".format(data))
                print(stdout, flush=True)
                print(stdout, file=log, flush=True)
            print(stdout, file=log, flush=True)

            print("---------- Running queries: see {} ----------".format(os.path.join(TSTDIR, "results", test_dir.split("_")[1], "{}-{}.log".format(data.split('/')[-1].split('.')[0], queries.split('/')[-1].split('.')[0]))), file=log, flush=True)
            proc = subprocess.Popen(["psql", DB, "-f", queries],
                                    bufsize=1, universal_newlines=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            stdout, stderr = proc.communicate()
            print(stdout, file=output, flush=True)

            print("---------- Dropping Test Schema", file=log, flush=True)
            subprocess.call(["psql", DB, "-f", os.path.join(TSTDIR, "tests", test_dir, "schema_drop.sql")], stdout=log, stderr=subprocess.STDOUT)

            print("---------- Dropping GeoCoord Type", file=log, flush=True)
            subprocess.call(["psql", DB, "-f", os.path.join(TSTDIR, "gcoord_drop.sql")], stdout=log, stderr=subprocess.STDOUT)

            print("---------- tearing-down database", file=log, flush=True)
            subprocess.call(["dropdb", DB], stdout=log, stderr=subprocess.STDOUT)

            output.close()

            print("---------- TEST RESULTS", file=log, flush=True)

            # remove timing data
            subprocess.call(["sed", "-i", "-E", r"s/(cost|actual time)=[^ ]*\s*/REMOVED_TIME /g", os.path.join(TSTDIR, "results", test_dir.split("_")[1], "{}-{}.log".format(data.split('/')[-1].split('.')[0], queries.split('/')[-1].split('.')[0]))])
            # remove coordinate 
            subprocess.call(["sed", "-i", "-E", r"s/\s*\(coord = [^:]+::geocoord\)/REMOVED_GCOORD/g", os.path.join(TSTDIR, "results", test_dir.split("_")[1], "{}-{}.log".format(data.split('/')[-1].split('.')[0], queries.split('/')[-1].split('.')[0]))])
            # replace query title 
            subprocess.call(["sed", "-i", "-E",r"/^.*QUERY.*$/ {N; s/^.*QUERY.*\n.*$/                                             QUERY PLAN                                             \n----------------------------------------------------------------------------------------------------/}", os.path.join(TSTDIR, "results", test_dir.split("_")[1], "{}-{}.log".format(data.split('/')[-1].split('.')[0], queries.split('/')[-1].split('.')[0]))])
            # remove timing data
            subprocess.call(["sed", "-i", "-E", r"s/\s*(Planning|Execution)\s*Time:\s*[^ ]*\s*[^ ]*\s*/REMOVED_TIME/g", os.path.join(TSTDIR, "results", test_dir.split("_")[1], "{}-{}.log".format(data.split('/')[-1].split('.')[0], queries.split('/')[-1].split('.')[0]))])
            # remove paths
            subprocess.call(["sed", "-i", "-E", r"s|psql:/.*/queries([0-9]*)\.sql:([0-9]*):|psql:/REMOVED_PATH/queries\1.sql:\2:|g", os.path.join(TSTDIR, "results", test_dir.split("_")[1], "{}-{}.log".format(data.split('/')[-1].split('.')[0], queries.split('/')[-1].split('.')[0]))])
            # remove widths
            subprocess.call(["sed", "-i", "-E", r"s/width=[0-9]+/REMOVED_WIDTH/g", os.path.join(TSTDIR, "results", test_dir.split("_")[1], "{}-{}.log".format(data.split('/')[-1].split('.')[0], queries.split('/')[-1].split('.')[0]))])

            if os.path.isfile(os.path.join(TSTDIR, "tests", test_dir, "expected-{}-{}.log".format(data.split('/')[-1].split('.')[0], queries.split('/')[-1].split('.')[0]))):
                if filecmp.cmp(os.path.join(TSTDIR, "results", test_dir.split("_")[1], "{}-{}.log".format(data.split('/')[-1].split('.')[0], queries.split('/')[-1].split('.')[0])),
                               os.path.join(TSTDIR, "tests", test_dir, "expected-{}-{}.log".format(data.split('/')[-1].split('.')[0], queries.split('/')[-1].split('.')[0])), shallow=False):
                    print("PASS: {} -- {} -- {}".format(test_dir.split("_")[1], data.split('/')[-1].split('.')[0], queries.split('/')[-1].split('.')[0]), flush=True)
                    print("PASS: {} -- {} -- {}".format(test_dir.split("_")[1], data.split('/')[-1].split('.')[0], queries.split('/')[-1].split('.')[0]), file=log, flush=True)
                else:
                    print("FAIL: {} -- {} -- {}".format(test_dir.split("_")[1], data.split('/')[-1].split('.')[0], queries.split('/')[-1].split('.')[0]), flush=True)
                    print("FAIL: {} -- {} -- {}".format(test_dir.split("_")[1], data.split('/')[-1].split('.')[0], queries.split('/')[-1].split('.')[0]), file=log, flush=True)

                    print("\trun: `diff {} {}`".format(os.path.join(TSTDIR, "results", test_dir.split("_")[1], "{}-{}.log".format(data.split('/')[-1].split('.')[0], queries.split('/')[-1].split('.')[0])),
                                                       os.path.join(TSTDIR, "tests", test_dir, "expected-{}-{}.log".format(data.split('/')[-1].split('.')[0], queries.split('/')[-1].split('.')[0]))), flush=True)
                    print("\trun: `diff {} {}`".format(os.path.join(TSTDIR, "results", test_dir.split("_")[1], "{}-{}.log".format(data.split('/')[-1].split('.')[0], queries.split('/')[-1].split('.')[0])),
                                                       os.path.join(TSTDIR, "tests", test_dir, "expected-{}-{}.log".format(data.split('/')[-1].split('.')[0], queries.split('/')[-1].split('.')[0]))), file=log, flush=True)
            else:
                print("SKIP: {} -- {} -- {}: No expected output file".format(test_dir.split("_")[1], data.split('/')[-1].split('.')[0], queries.split('/')[-1].split('.')[0]), flush=True)
                print("SKIP: {} -- {} -- {}: No expected output file".format(test_dir.split("_")[1], data.split('/')[-1].split('.')[0], queries.split('/')[-1].split('.')[0]), file=log, flush=True)

            print("|---------- END TEST -- {}  -- {} -- {} ----------|".format(test_dir.split("_")[1], data.split('/')[-1].split('.')[0], queries.split('/')[-1].split('.')[0]), file=log, flush=True)


def set_env():
    # Get current user
    global USER
    USER = os.getenv("USER")

    # Get users localstorage directory
    global LOCALSTORAGE
    LOCALSTORAGE = os.path.join("/", "localstorage", USER)
    os.putenv("LOCALSTORAGE",   LOCALSTORAGE)

    # Get users Postgres install directory
    global PGHOME
    PGHOME = os.path.join(LOCALSTORAGE, "pgsql")
    os.putenv("PGHOME", PGHOME)

    if not os.path.exists(PGHOME):
        raise NotADirectoryError("Postgres source code directory must exist: \"{}\"".format(PGHOME))

    # Create a tmp directory to hold the Postgres server
    global PGDATA
    PGDATA = tempfile.mkdtemp()
    os.putenv("PGDATA", PGDATA)

    atexit.register(remove_postgres_data)

    # alias PGDATA
    global PGHOST
    PGHOST = PGDATA
    os.putenv("PGHOST", PGHOST)

    # Get the current working directory as the home for tests
    global TSTDIR
    TSTDIR = os.path.abspath(os.path.realpath(os.getcwd()))
    os.putenv("TSTDIR", TSTDIR)

    global PGPORT
    PGPORT = "5432"
    os.putenv("PGPORT", PGPORT)

    # Add Postgres lib to lib-path
    global LD_LIBRARY_PATH
    LD_LIBRARY_PATH = "{}:{}".format(os.path.join(PGHOME, "lib"), os.getenv("LD_LIBRARY_PATH", default=""))
    os.putenv("LD_LIBRARY_PATH", LD_LIBRARY_PATH)

    # Add Postgres bin to path
    global PATH
    PATH = "{}:{}:{}".format(os.path.join(PGHOME, "bin"), os.path.join("home", "cs9315"), os.getenv("PATH"))
    os.putenv("PATH", PATH)

    # Postgres source code directory
    global SRCDIR
    SRCDIR = os.path.join(LOCALSTORAGE, "postgresql-15.1", "src")
    os.putenv("SRCDIR", SRCDIR)

    if not os.path.exists(SRCDIR):
        raise NotADirectoryError("Postgres source code directory must exist: \"{}\"".format(SRCDIR))

    # Postgres database name
    global DB
    DB = "gcoord-test"
    os.putenv("DB", DB)

    # hack to hopefully stabilize sort order
    os.putenv("LC_COLLATE", "POSIX")
    os.putenv("LC_CTYPE",   "POSIX")
    os.putenv("LC_ALL",     "POSIX")


def create_logs():
    if os.path.isfile(os.path.join(TSTDIR, "test.log")):
        os.remove(os.path.join(TSTDIR, "test.log"))
    global log
    log = open(os.path.join(TSTDIR, "test.log"), "w")
    atexit.register(log.close)

    if os.path.isfile(os.path.join(TSTDIR, "pg.log")):
        os.remove(os.path.join(TSTDIR, "pg.log"))


def check_user_files():
    if not os.path.isfile(os.path.join(TSTDIR, "gcoord.c")):
        raise FileNotFoundError("No gcoord.c file: \"{}\"".format(TSTDIR))

    if not os.path.isfile(os.path.join(TSTDIR, "gcoord.source")):
        raise FileNotFoundError("No gcoord.source file: \"{}\"".format(TSTDIR))


def remove_junk_files():
    if os.path.isfile(os.path.join(TSTDIR, "gcoord.so")):
        print("Info: removing gcoord.so from {}".format(TSTDIR), file=log, flush=True)
        os.remove(os.path.join(TSTDIR, "gcoord.so"))

    if os.path.isfile(os.path.join(TSTDIR, "gcoord.o")):
        print("Info: removing gcoord.o from {}".format(TSTDIR), file=log, flush=True)
        os.remove(os.path.join(TSTDIR, "gcoord.o"))

    if os.path.isfile(os.path.join(TSTDIR, "gcoord")):
        print("Info: removing gcoord from {}".format(TSTDIR), file=log, flush=True)
        os.remove(os.path.join(TSTDIR, "gcoord"))

    if os.path.isfile(os.path.join(TSTDIR, "gcoord.sql")):
        print("Info: removing gcoord.sql from {}".format(TSTDIR), file=log, flush=True)
        os.remove(os.path.join(TSTDIR, "gcoord.sql"))

    if os.path.isfile(os.path.join(TSTDIR, "gcoord.bc")):
        print("Info: removing gcoord.bc from {}".format(TSTDIR), file=log, flush=True)
        os.remove(os.path.join(TSTDIR, "gcoord.bc"))


def remove_postgres_data():
    if os.path.isdir(PGDATA):
        shutil.rmtree(PGDATA)


def kill_postgres_if_running():
    proc = subprocess.Popen(["pg_ctl", "status"],
                            bufsize=1, universal_newlines=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    stdout, stderr = proc.communicate()
    if stdout.startswith("pg_ctl: server is running"):
        subprocess.call(["pg_ctl", "stop"], stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)


def make_user_files():
    print("|---------- running `make` ----------|", file=log, flush=True)
    proc = subprocess.Popen(["make"],
                            bufsize=1, universal_newlines=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    stdout, stderr = proc.communicate()
    if "error:" in stdout:
        print("Error: build error from Postgres MakeFile", flush=True, end="\n\n")
        print(stdout, flush=True)
        print(stdout, file=log, flush=True)
        sys.exit(1)
    if "warning:" in stdout:
        print("Warning: build warning from Postgres MakeFile, check test.log for details", flush=True, end="\n\n")
    print(stdout, file=log, flush=True)

    atexit.register(remove_junk_files)


def setup_postgres_sever():
    print("|---------- setting-up database server ----------|", file=log, flush=True)
    subprocess.call(["initdb", "-A", "trust"], stdout=log, stderr=subprocess.STDOUT)

    # Setup the config file
    with open(os.path.join(PGDATA, "postgresql.conf"), "a") as conf:
        print("""\
    listen_addresses = ''
    port = 5432
    max_connections = 10
    max_wal_senders = 4
    unix_socket_directories = '{}'
    """.format(PGDATA), file=conf)

    print("|---------- starting database server ----------|", file=log, flush=True)
    proc = subprocess.Popen(["pg_ctl", "-D", PGDATA, "start", "-l", os.path.join(TSTDIR, "pg.log")],
                            bufsize=1, universal_newlines=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    stdout, stderr = proc.communicate()
    if not stdout.endswith("server started\n"):
        print("Error: server could not be started", flush=True)
        print(stdout, flush=True)
        print(stdout, file=log, flush=True)
        sys.exit(1)
    print(stdout, file=log, flush=True)

    atexit.register(kill_postgres_if_running)

    subprocess.call(["dropdb", "--if-exists", DB], stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)


def main():
    if socket.gethostname() != "nw-syd-vxdb":
        print("""\
Error: Please run on vxdb
run:
\t `ssh nw-syd-vxdb`
\t `source /localstorage/$USER/env`
\t `cd /localstorage/$USER/testing`
\t `python3 {}`
""".format(' '.join(sys.argv)), flush=True)
        return 1

    signal.signal(signal.SIGINT, lambda x, y: sys.exit(1))

    set_env()
    create_logs()
    check_user_files()
    remove_junk_files()
    kill_postgres_if_running()

    make_user_files()
    setup_postgres_sever()
    run_tests()

    kill_postgres_if_running()
    remove_junk_files()


if __name__ == '__main__':
    sys.exit(main())
