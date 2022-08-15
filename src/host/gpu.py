import subprocess
import re
import threading


# This is platform dependant macOS M1 and provided as an example
# For this module to work powermetrics must be added to sudoers
class GpuUsage(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        self.usage = 0

    def run(self):
        while True:
            p = subprocess.Popen("sudo powermetrics --samplers gpu_power -i1000 -n1 | grep 'GPU active residency'",
                                 stdout=subprocess.PIPE, shell=True)
            (output, err) = p.communicate()
            p.wait()
            match = re.search("residency:\s*(.*?)%", output.decode("utf-8"))
            if match is not None:
                self.usage = float(match.group(1))
