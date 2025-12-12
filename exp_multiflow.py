from mininet.net import Mininet
from mininet.topo import Topo
from mininet.node import OVSKernelSwitch, Host
from mininet.cli import CLI
from mininet.link import TCLink
from mininet.log import setLogLevel, info
import time

class MultiFlowTopo(Topo):
    def build(self):
        # 서버 1개, 클라이언트 5개
        server = self.addHost('h1', cls=Host)
        clients = [self.addHost(f'h{i}', cls=Host) for i in range(2, 7)]  # h2~h6
        s1 = self.addSwitch('s1', cls=OVSKernelSwitch)

        link_opts = dict(
            cls=TCLink,
           # bw=1000,        # 1 Gbit/s
            delay='50ms',    # 높은 지연
            jitter='10ms',   # 지연 변동
            loss=1         # 링크 오류로 인한 높은 손실
        )

        self.addLink(server, s1, **link_opts)
        for h in clients:
            self.addLink(h, s1, **link_opts)

def runExperiment(cc_algo='reno_bwe', duration=30):
    topo = MultiFlowTopo()
    net = Mininet(topo=topo, autoSetMacs=True, build=True)
    net.start()

    server = net.get('h1')
    clients = [net.get(f'h{i}') for i in range(2, 7)]  # h2~h6

    info(f"*** Set TCP CC to {cc_algo}\n")
    for h in net.hosts:
        h.cmd(f"sysctl -w net.ipv4.tcp_congestion_control={cc_algo} > /dev/null")

    server_ip = server.IP()

    info("*** Kill old iperf3 servers (if any)\n")
    server.cmd("pkill iperf3")

    # 🔹 포트 5개에 대해 서버 5개 실행: 5201 ~ 5205
    info("*** Start 5 iperf3 servers on h1 (ports 5201~5205)\n")
    for i in range(5):
        port = 5201 + i
        server.cmd(f"iperf3 -s -p {port} > /tmp/iperf3_s_{port}.log 2>&1 &")

    time.sleep(1)

    # 🔹 클라이언트 5개를 각기 다른 포트로 연결
    info("*** Start 5 concurrent iperf3 clients (h2~h6)\n")
    for idx, c in enumerate(clients, start=2):
        port = 5200 + idx       # h2→5202, h3→5203, …, h6→5206
        logFile = f"/tmp/iperf3_h{idx}_{cc_algo}.json"
        cmd = f"iperf3 -J -c {server_ip} -p {port} -t {duration} > {logFile} &"
        info(f"h{idx}: {cmd}\n")
        c.cmd(cmd)
        time.sleep(0.2)  # 살짝 간격 두기 (너무 동시 연결하면 로그 꼬일 위험 감소)

    info(f"*** Running {duration} seconds...\n")
    time.sleep(duration + 3)

    info("*** iperf3 finished. You can now run the analyzer script.\n")
    CLI(net)
    net.stop()

if __name__ == "__main__":
    setLogLevel('info')
    # 예: runExperiment('reno'), runExperiment('reno_custom') 각각 실행
    runExperiment('reno', duration=30)

