#include <linux/module.h>
#include <linux/kernel.h>
#include <net/tcp.h>

/*
 * Reno + Westwood 스타일 하이브리드
 * - pkts_acked: 대역폭(BWE) + 최소 RTT 추정
 * - ssthresh: 손실 시 cwnd/2 대신 BDP 기반으로 설정
 * - cong_avoid: Reno 증가 (공정성 유지)
 *
 * reno_custom (원래 reno_bwe)
 */

struct reno_bwe {
    u32 min_rtt_us;
    u32 bwe_pps;
    u32 bwe_filt_pps;
    u32 spare;
};

static void reno_custom_init(struct sock *sk)
{
    struct reno_bwe *ca = inet_csk_ca(sk);

    ca->min_rtt_us   = 0x7fffffff;
    ca->bwe_pps      = 0;
    ca->bwe_filt_pps = 0;
    ca->spare        = 0;
}

static void reno_custom_pkts_acked(struct sock *sk, const struct ack_sample *sample)
{
    struct reno_bwe *ca = inet_csk_ca(sk);
    s32 rtt_us = sample->rtt_us;
    u32 pkts   = sample->pkts_acked;
    u64 inst_pps;

    if (rtt_us <= 0 || pkts == 0)
        return;

    /* RTT 업데이트 */
    if (ca->min_rtt_us == 0x7fffffff || (u32)rtt_us < ca->min_rtt_us)
        ca->min_rtt_us = (u32)rtt_us;

    /* BWE = pkts / RTT */
    inst_pps = (u64)pkts * USEC_PER_SEC;
    do_div(inst_pps, (u32)rtt_us);

    ca->bwe_pps = (u32)inst_pps;

    /* EWMA 필터 */
    if (ca->bwe_filt_pps == 0)
        ca->bwe_filt_pps = ca->bwe_pps;
    else
        ca->bwe_filt_pps = (7 * ca->bwe_filt_pps + ca->bwe_pps) >> 3;
}

static u32 reno_custom_ssthresh(struct sock *sk)
{
    const struct tcp_sock *tp = tcp_sk(sk);
    struct reno_bwe *ca = inet_csk_ca(sk);

    u32 reno_half = max(tp->snd_cwnd >> 1U, 2U);

    if (ca->min_rtt_us == 0x7fffffff || ca->bwe_filt_pps == 0)
        return reno_half;

    /* BDP = BWE * min_rtt */
    {
        u64 bdp_pkts = (u64)ca->bwe_filt_pps * (u64)ca->min_rtt_us;
        u32 target_cwnd;

        do_div(bdp_pkts, USEC_PER_SEC);

        if (bdp_pkts < 2)
            target_cwnd = 2;
        else if (bdp_pkts > (u64)tp->snd_cwnd * 4U)
            target_cwnd = tp->snd_cwnd * 4U;
        else
            target_cwnd = (u32)bdp_pkts;

        return max(target_cwnd, 2U);
    }
}

static void reno_custom_cong_avoid(struct sock *sk, u32 ack, u32 acked)
{
    struct tcp_sock *tp = tcp_sk(sk);
    struct reno_bwe *ca = inet_csk_ca(sk);

    if (!tcp_is_cwnd_limited(sk))
        return;

    if (tcp_in_slow_start(tp)) {
        acked = tcp_slow_start(tp, acked);
        if (!acked)
            return;
    }

    tcp_cong_avoid_ai(tp, tp->snd_cwnd, acked);

    /* cwnd가 BDP의 2배 이상이면 제한 */
    if (ca->min_rtt_us != 0x7fffffff && ca->bwe_filt_pps > 0) {
        u64 bdp_pkts = (u64)ca->bwe_filt_pps * (u64)ca->min_rtt_us;
        u32 cap;

        do_div(bdp_pkts, USEC_PER_SEC);
        cap = (u32)bdp_pkts * 2U;

        if (cap > 0 && tp->snd_cwnd > cap)
            tp->snd_cwnd = cap;
    }

    tp->snd_cwnd = min(tp->snd_cwnd, tp->snd_cwnd_clamp);
}

static u32 reno_custom_undo_cwnd(struct sock *sk)
{
    return tcp_sk(sk)->snd_cwnd;
}


static struct tcp_congestion_ops tcp_reno_custom = {
    .init       = reno_custom_init,
    .ssthresh   = reno_custom_ssthresh,
    .cong_avoid = reno_custom_cong_avoid,
    .undo_cwnd  = reno_custom_undo_cwnd,
    .pkts_acked = reno_custom_pkts_acked,

    .owner      = THIS_MODULE,
    .name       = "reno_custom",   /* ⭐ 모듈 이름 변경! */
};

static int __init reno_custom_module_init(void)
{
    int ret;

    BUILD_BUG_ON(sizeof(struct reno_bwe) > ICSK_CA_PRIV_SIZE);

    ret = tcp_register_congestion_control(&tcp_reno_custom);
    if (ret)
        pr_err("reno_custom: registration failed (%d)\n", ret);
    else
        pr_info("reno_custom: registered\n");
    return ret;
}

static void __exit reno_custom_module_exit(void)
{
    tcp_unregister_congestion_control(&tcp_reno_custom);
    pr_info("reno_custom: unregistered\n");
}

module_init(reno_custom_module_init);
module_exit(reno_custom_module_exit);

MODULE_AUTHOR("mingyu");
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("Modified TCP Reno (reno_custom) with Westwood-style BWE");

