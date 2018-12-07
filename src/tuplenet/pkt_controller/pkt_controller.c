#include <stdio.h>
#include <stdarg.h>
#include <unistd.h>
#include <netinet/ip.h>
#include <arpa/inet.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <limits.h>
#include <sys/time.h>
#include <errno.h>
#include "openvswitch/ofp-actions.h"
#include "openvswitch/ofp-msgs.h"
#include "openvswitch/ofp-print.h"
#include "openvswitch/ofp-util.h"
#include "openvswitch/meta-flow.h"
#include "openvswitch/util.h"
#include "openvswitch/ofp-errors.h"
#include "openvswitch/match.h"
#include "openflow/openflow-1.0.h"
#include "openvswitch/vlog.h"
#include "ovs_side_func_dec.h"
#if HAVE_OPENVSWITCH_OFP_PACKET_H
#include "openvswitch/ofp-packet.h"
#endif
#if HAVE_OPENVSWITCH_OFP_SWITCH_H
#include "openvswitch/ofp-switch.h"
#endif

typedef int tp_status;
#define TP_STATUS_OK 0
#define TP_STATUS_FAIL -1
#define TP_STATUS_ERR_PKT -2
#define TP_STATUS_ERR_FIFO -3
#define TP_STATUS_MEM_FAIL -4

#define DSCP_DEFAULT (IPTOS_PREC_INTERNETCONTROL >> 2)

#define ETH_TYPE_ARP 0x0806
#define ARP_HRD_ETHERNET 1
#define ARP_PRO_IP 0x0800
#define ETH_TYPE_IP 0x0800

#define PID_STR_MAX_LEN 32
#define MAX_STR_BUF_LEN 1024

#define MAX_CONN_RETRY_TIME 100

#define PKT_IN_OPCODE_RARP 1
#define PKT_IN_OPCODE_BEG_ARP 2
#define PKT_IN_OPCODE_TRACE 3
#define PKT_IN_OPCODE_UNKNOW_DST 4

#define REG_SRC_IDX 0
#define REG_DST_IDX 1
#define REG_FLAG_IDX 10

#define OPCODE_ARP_STR "arp"
#define OPCODE_TRACE_STR "trace"
#define OPCODE_UNKNOW_DST_STR "unknow_dst"

#define TM_HASHMAP_EXPIRE_MS 100

#define MAX(a,b) ((a) > (b) ? (a) : (b))
#define MIN(a,b) ((a) > (b) ? (b) : (a))

const char* TUPLENET_DEFAULT_RUN_PATH = "/var/run/tuplenet";
const char* TUPLENET_RUNDIR = "TUPLENET_RUNDIR";
const char* OVS_RUNDIR = "OVS_RUNDIR";
const char* TUPLENET_PIPE_NAME = "pkt_controller_pipe";

VLOG_DEFINE_THIS_MODULE(pkt_controller);

struct arp_header {
    ovs_be16    hdr;
    ovs_be16    pro;
    uint8_t     hln;
    uint8_t     pln;
    ovs_be16    arp_op;
    uint8_t     arp_sha[6];
    ovs_be32    arp_sip;
    uint8_t     arp_tha[6];
    ovs_be32    arp_tip;
} __attribute__((packed));

struct ip_header {
    uint8_t     ip_ihl_ver;
    uint8_t     ip_tos;
    ovs_be16    ip_tot_len;
    ovs_be16    ip_id;
    ovs_be16    ip_frag_off;
    uint8_t     ip_ttl;
    uint8_t     ip_proto;
    ovs_be16    ip_csum;
    ovs_be32    ip_src;
    ovs_be32    ip_dst;
} __attribute__((packed));

struct eth_header {
    uint8_t     eth_dst[6];
    uint8_t     eth_src[6];
    ovs_be16    type;
} __attribute__((packed));

struct action_header {
    ovs_be32    opcode;
    uint8_t     pad[4];
};

typedef struct tm_hash_node {
    struct timeval tm;
} tm_hash_node;

static struct tm_hash_node *tm_expire_hashmap = NULL;
static uint32_t len_tm_expire_hashmap = 65535;
static struct rconn *swconn = NULL;
static unsigned int conn_seq_no = 0;
static int tp_fifo_fd = -1;
static struct vlog_rate_limit rl = VLOG_RATE_LIMIT_INIT(50, 100);

static inline uint64_t
ntohll(ovs_be64 n)
{
    return htonl(1) == 1 ? n : ((uint64_t) ntohl(n) << 32) | ntohl(n >> 32);
}

static ovs_be32 queue_msg(struct ofpbuf *msg);

static tp_status
init_tm_expire_hashmap(uint32_t num)
{
    len_tm_expire_hashmap = MIN(num, len_tm_expire_hashmap);
    tm_expire_hashmap = calloc(sizeof(tm_hash_node), len_tm_expire_hashmap);
    if (tm_expire_hashmap) {
        return TP_STATUS_OK;
    }
    return TP_STATUS_MEM_FAIL;
}

static bool
_is_expire(struct timeval *tm_current, struct timeval *tm_previous, int ms)
{
    return 1000 * 1000 * (tm_current->tv_sec - tm_previous->tv_sec) +
              tm_current->tv_usec - tm_previous->tv_usec > ms * 1000 ? 1 : 0;
}

static tp_status
tmhashmap_add_node(uint32_t key)
{
    struct timeval tm;
    gettimeofday(&tm, NULL);
    int idx = key % len_tm_expire_hashmap;
    if (_is_expire(&tm, &(tm_expire_hashmap[idx].tm), TM_HASHMAP_EXPIRE_MS)) {
        tm_expire_hashmap[idx].tm = tm;
        return TP_STATUS_OK;
    }

    return TP_STATUS_FAIL;
}

static void
reload_metadata(struct ofpbuf *ofpacts, const struct match *md)
{
    enum mf_field_id md_fields[] = {
            MFF_REG0, MFF_REG1, MFF_REG2, MFF_REG3, MFF_REG4,
            MFF_REG5, MFF_REG6, MFF_REG7, MFF_REG8, MFF_REG9,
            MFF_REG10, MFF_REG11, MFF_REG12, MFF_REG13,
            MFF_REG14, MFF_REG15,

            MFF_METADATA,
            MFF_TUN_SRC, MFF_TUN_DST, MFF_TUN_ID
    };

    for (size_t i = 0;
         i < sizeof(md_fields)/sizeof(enum mf_field_id)/*number of md_fields*/;
         i++) {
        const struct mf_field *field = mf_from_id(md_fields[i]);
        if (!mf_is_all_wild(field, &md->wc)) {
            union mf_value value;
            mf_get_value(field, &md->flow, &value);
            ofpact_put_set_field(ofpacts, field, &value, NULL);
        }
    }
}

int
create_fifo(char *path)
{
    int fifo_fd = -1;
    if (access(path, F_OK) == -1) {
        if (mkfifo(path, 0644)  != 0) {
            VLOG_WARN("cannot create fifo file:%s", path);
            return -1;
        }
    }
    fifo_fd = open(path, O_WRONLY);
    return fifo_fd;
}

static int
_write_fifo(char *buf, uint32_t len)
{
    uint32_t n = 0;
    if (len == 0) {
        VLOG_WARN("buffer len is zero");
        return 0;
    }
    if (tp_fifo_fd == -1) {
        VLOG_ERR("pipe fd is invalid");
        return -1;
    }

    n = write(tp_fifo_fd, buf, len);
    if (n == -1) {
        VLOG_WARN("failed to write data to fifo pipe, errno:%d", errno);
    }
    return n;
}

static tp_status
write_tp_fifo(char *buf, uint32_t buf_size, char *fmt, ...)
{
    va_list va;
    va_start(va, fmt);
    int n = vsnprintf(buf, buf_size, fmt, va);
    va_end(va);
    if (n < 0 || n >= buf_size) {
        VLOG_WARN("faild to write data into buffer");
        return TP_STATUS_FAIL;
    }

    int blen = strnlen(buf, buf_size);
    n = _write_fifo(buf, blen);
    if (blen != n) {
        VLOG_WARN("failed to write buffer to tuplenet fifo");
        return TP_STATUS_ERR_FIFO;
    }
    return TP_STATUS_OK;
}

void
tunnel_init(void)
{
    swconn = rconn_create(5, 0, DSCP_DEFAULT, 1 << OFP13_VERSION);
    conn_seq_no = 0;
}

static ovs_be32
queue_msg(struct ofpbuf *msg)
{
    const struct ofp_header *oh = msg->data;
    ovs_be32 xid = oh->xid;

    rconn_send(swconn, msg, NULL);
    return xid;
}

static void
tunnel_setup(struct rconn *swconn)
{
    queue_msg(ofpraw_alloc(OFPRAW_OFPT_GET_CONFIG_REQUEST,
                           rconn_get_version(swconn), 0));
#if HAVE_OFPUTIL_ENCODE_SET_PACKET_IN_FORMAT
    queue_msg(ofputil_encode_set_packet_in_format(rconn_get_version(swconn),
                                                  OFPUTIL_PACKET_IN_NXT2));
#else
    queue_msg(ofputil_make_set_packet_in_format(rconn_get_version(swconn),
                                                NXPIF_NXT_PACKET_IN2));
#endif
}

static void
set_switch_config(struct rconn *swconn,
                  const struct ofputil_switch_config *config)
{
    enum ofp_version version = rconn_get_version(swconn);
    struct ofpbuf *request = ofputil_encode_set_config(config, version);
    queue_msg(request);
}

static tp_status
process_unknow_dst_pkt(struct ofputil_packet_in *pin, struct ofpbuf *userdata)
{
    uint32_t datapath_id = ntohll(pin->flow_metadata.flow.metadata);
    tp_status status;
    VLOG_DBG_RL(&rl, "receive a unknow destination packet, datapath_id=%u",
                datapath_id);

    char tp_buf[128];
    struct eth_header *eth_hdr = pin->packet;
    if (eth_hdr->type == htons(ETH_TYPE_ARP)) {
        struct arp_header *arp_hdr = pin->packet + sizeof(struct eth_header);
        if (tmhashmap_add_node(ntohl(arp_hdr->arp_tip)) != TP_STATUS_OK) {
            VLOG_INFO_RL(&rl, "we may receive same arp packet before in %ums, "
                         "ignore this packet", TM_HASHMAP_EXPIRE_MS);
            return TP_STATUS_OK;
        }

        status = write_tp_fifo(tp_buf, sizeof(tp_buf),
                               "%s,%u,%u;", OPCODE_UNKNOW_DST_STR,
                               datapath_id, ntohl(arp_hdr->arp_tip));
        if (status != TP_STATUS_OK) {
            return status;
        }
    } else if (eth_hdr->type == htons(ETH_TYPE_IP)) {
        struct ip_header *ip_hdr = (struct ip_header*)((char*)eth_hdr +
                                                    sizeof(struct eth_header));
        if (tmhashmap_add_node(ntohl(ip_hdr->ip_dst)) != TP_STATUS_OK) {
            VLOG_INFO_RL(&rl, "we may receive same ip packet before in 100ms, "
                      "ignore this packet");
            return TP_STATUS_OK;
        }

        status = write_tp_fifo(tp_buf, sizeof(tp_buf),
                               "%s,%u,%u;", OPCODE_UNKNOW_DST_STR,
                               datapath_id, ntohl(ip_hdr->ip_dst));
        if (status != TP_STATUS_OK) {
            return status;
        }
    } else {
        VLOG_WARN("invalid type in eth header:0x%x, maybe a vlan packet",
                  eth_hdr->type);
        //would not process vlan packet
        return TP_STATUS_ERR_PKT;
    }

    return TP_STATUS_OK;
}

static tp_status
process_arp_pkt(struct ofputil_packet_in *pin)
{
    tp_status status;
    uint32_t datapath_id = ntohll(pin->flow_metadata.flow.metadata);
    VLOG_DBG_RL(&rl, "receive arp packet, datapath_id=%u", datapath_id);

    struct eth_header *eth = pin->packet;
    if (eth->type != htons(ETH_TYPE_ARP)) {
        //would not process vlan packet
        VLOG_WARN("invalid type in eth header:0x%x, maybe a vlan packet",
                  eth->type);
        return TP_STATUS_ERR_PKT;
    }

    char tp_buf[128];
    struct arp_header *arp = pin->packet + sizeof(struct eth_header);
    status = write_tp_fifo(tp_buf, sizeof(tp_buf),
                           "%s,%u,%02x:%02x:%02x:%02x:%02x:%02x,%u;",
                           OPCODE_ARP_STR, datapath_id,
                           arp->arp_sha[0], arp->arp_sha[1], arp->arp_sha[2],
                           arp->arp_sha[3], arp->arp_sha[4], arp->arp_sha[5],
                           ntohl(arp->arp_sip));
    if (status != TP_STATUS_OK) {
        return status;
    }
    return status;
}

static tp_status
process_beg_arp(struct ofputil_packet_in *pin, struct ofpbuf *userdata)
{
    tp_status status;
    uint32_t datapath_id = ntohll(pin->flow_metadata.flow.metadata);
    VLOG_DBG_RL(&rl, "receive ask generate arp command, datapath_id=%u",
                datapath_id);

    struct eth_header *pkt_in_eth_hdr = pin->packet;
    if (pkt_in_eth_hdr->type != htons(ETH_TYPE_IP)) {
        VLOG_WARN("Not a IP packet, proto:0x%x", pkt_in_eth_hdr->type);
        return TP_STATUS_ERR_PKT;
    }

    uint64_t ofpacts_stub[4096 / 8];
    struct ofpbuf ofpacts = OFPBUF_STUB_INITIALIZER(ofpacts_stub);
    enum ofp_version version = rconn_get_version(swconn);
    enum ofperr error;

    char packet_data[128];
    struct eth_header *po_eth = (struct eth_header*)(packet_data);
    struct arp_header *po_arp = (struct arp_header*)(packet_data +
                                                     sizeof(struct eth_header));
    memcpy(po_eth->eth_src, pkt_in_eth_hdr->eth_src, sizeof(po_eth->eth_src));
    memset(po_eth->eth_dst, 0xff, sizeof(po_eth->eth_dst));
    po_eth->type = htons(ETH_TYPE_ARP);
    po_arp->hdr = htons(ARP_HRD_ETHERNET);
    po_arp->pro = htons(ARP_PRO_IP);
    po_arp->hln = sizeof(po_arp->arp_sha);
    po_arp->pln = sizeof(po_arp->arp_sip);
    po_arp->arp_op = htons(1);
    memcpy(po_arp->arp_sha, po_eth->eth_src, sizeof(po_arp->arp_sha));
    // we store the this hop ip and next hop ip in reg3 & reg2
    // TODO ntohl ????!
    po_arp->arp_sip = ntohl(pin->flow_metadata.flow.regs[3]);
    memset(po_arp->arp_tha, 0, sizeof(po_arp->arp_tha));
    po_arp->arp_tip = ntohl(pin->flow_metadata.flow.regs[2]);

    // tracing mark occupies the second bit. we should clean it
    // we don't want a arp packet bring a tracing mark
    pin->flow_metadata.flow.regs[REG_FLAG_IDX] &= 0xfffd;

    reload_metadata(&ofpacts, &pin->flow_metadata);
    error = ofpacts_pull_openflow_actions(userdata, userdata->size,
                                          version, NULL, NULL,
                                          &ofpacts);
    if (error) {
        VLOG_WARN("failed to parse arp actions:%s\n",
                  ofperr_to_string(error));
        goto fail_parse_action;
    }
    struct ofputil_packet_out pkt_out = {
        .packet = (void*)po_eth,
        .packet_len = sizeof(struct eth_header) + sizeof(struct arp_header),
        .buffer_id = UINT32_MAX,
        .ofpacts = ofpacts.data,
        .ofpacts_len = ofpacts.size,
    };

    match_set_in_port(&pkt_out.flow_metadata, OFPP_CONTROLLER);
    enum ofputil_protocol proto = ofputil_protocol_from_ofp_version(version);
    queue_msg(ofputil_encode_packet_out(&pkt_out, proto));
    status = TP_STATUS_OK;

fail_parse_action:
    ofpbuf_uninit(&ofpacts);
    return status;
}

static tp_status
process_trace(struct ofputil_packet_in *pin)
{
    tp_status status;
    static uint32_t seq_n = 0;
    uint8_t table_id = pin->table_id;
    uint32_t src_port_id = pin->flow_metadata.flow.regs[REG_SRC_IDX];
    uint32_t dst_port_id = pin->flow_metadata.flow.regs[REG_DST_IDX];
    uint32_t flag = pin->flow_metadata.flow.regs[REG_FLAG_IDX];
    uint32_t datapath_id = ntohll(pin->flow_metadata.flow.metadata);
    VLOG_DBG_RL(&rl, "receive tracing packet, datapath_id=%u", datapath_id);

    char tp_buf[128];
    status = write_tp_fifo(tp_buf, sizeof(tp_buf),
                           "%s,%u,%u,%u,%u,%u,%u,%u;",
                           OPCODE_TRACE_STR,
                           table_id, datapath_id,
                           flag, src_port_id, dst_port_id,
                           ntohl(pin->flow_metadata.flow.tunnel.ip_src), seq_n);
    if (status != TP_STATUS_OK) {
        return status;
    }

    seq_n++;
    return status;
}

static tp_status
process_packet_in(const struct ofp_header *msg)
{
    tp_status status;
    struct ofputil_packet_in pin;
    struct ofpbuf continuation;
    enum ofperr error = ofputil_decode_packet_in(msg, true, NULL, NULL, &pin,
                                                 NULL, NULL, &continuation);
    if (error || pin.reason != OFPR_ACTION) {
        return TP_STATUS_ERR_PKT;
    }

    struct ofpbuf userdata = ofpbuf_const_initializer(pin.userdata,
                                                      pin.userdata_len);
    const struct action_header *ah = ofpbuf_pull(&userdata, sizeof *ah);
    if (!ah) {
        VLOG_WARN("packet-in userdata lacks action header");
        return TP_STATUS_ERR_PKT;
    }

    switch (ntohl(ah->opcode)) {
    case PKT_IN_OPCODE_RARP:
        status = process_arp_pkt(&pin);
        break;
    case PKT_IN_OPCODE_BEG_ARP:
        status = process_beg_arp(&pin, &userdata);
        break;
    case PKT_IN_OPCODE_TRACE:
        status = process_trace(&pin);
        break;
    case PKT_IN_OPCODE_UNKNOW_DST:
        status = process_unknow_dst_pkt(&pin, &userdata);
        break;
    default:
        VLOG_WARN("unknow command number");
        status = TP_STATUS_FAIL;
    }
    return status;
}

static void
tunnel_recv(const struct ofp_header *oh, enum ofptype type)
{
    if (type == OFPTYPE_ECHO_REQUEST) {
        VLOG_INFO("receive echo request");
#if HAVE_OFPUTIL_ENCODE_ECHO_REPLY
        queue_msg(ofputil_encode_echo_reply(oh));
#else
        queue_msg(make_echo_reply(oh));
#endif
    } else if (type == OFPTYPE_GET_CONFIG_REPLY) {
        struct ofputil_switch_config config;
        VLOG_INFO("receive config reply");
        ofputil_decode_get_config_reply(oh, &config);
        config.miss_send_len = UINT16_MAX;
        set_switch_config(swconn, &config);
    } else if (type == OFPTYPE_PACKET_IN) {
        tp_status status = process_packet_in(oh);
        if (status != TP_STATUS_OK) {
            VLOG_WARN("error in processing in-packet");
        }
    }
}

static tp_status
ovs_connect_br_mgmt(char *target)
{
    uint32_t retry_n = 0;
    tunnel_init();
    rconn_connect(swconn, target, target);
    usleep(100 * 1000);
    rconn_run(swconn);
    while (!rconn_is_connected(swconn)) {
        if (retry_n > MAX_CONN_RETRY_TIME) {
            VLOG_ERR("failed to connect the bridge %s", target);
            return TP_STATUS_FAIL;
        }
        rconn_connect(swconn, target, target);
        usleep(100 * 1000);
        rconn_run(swconn);
        retry_n++;
    }

    return TP_STATUS_OK;
}


static tp_status
init_log(char *filename)
{
    int ret = 0;
    char tuplenet_logpath[MAX_STR_BUF_LEN];
    const char *tuplenet_logdir = getenv("TUPLENET_LOGDIR");
    if (tuplenet_logdir == NULL || strlen(tuplenet_logdir) == 0) {
        // no need to output to a file
        vlog_set_levels(NULL, VLF_ANY_DESTINATION, VLL_DBG);
        VLOG_INFO("set no log file");
        return TP_STATUS_OK;
    }

    int n = snprintf(tuplenet_logpath, sizeof(tuplenet_logpath), "%s/%s.log",
                     tuplenet_logdir, filename);
    if (n < 0 || n >= MAX_STR_BUF_LEN) {
        VLOG_ERR("failed to write tuplenet logpath");
        return TP_STATUS_FAIL;
    }

    vlog_set_levels(NULL, VLF_ANY_DESTINATION, VLL_DBG);
    ret = vlog_set_log_file(tuplenet_logpath);
    if (ret != 0) {
        VLOG_ERR("cannot config log file");
        return TP_STATUS_FAIL;
    }
    ret = vlog_reopen_log_file();
    if (ret != 0) {
        VLOG_ERR("cannot reopen log file");
        return TP_STATUS_FAIL;
    }
    VLOG_INFO("log file is %s", tuplenet_logpath);
    return TP_STATUS_OK;
}

tp_status
init_env()
{
    tp_status status = TP_STATUS_OK;

    if (init_tm_expire_hashmap(65535) != TP_STATUS_OK) {
        VLOG_ERR("failed to init simple hashmap");
        return TP_STATUS_FAIL;
    }

    const char *tuplenet_rundir = getenv(TUPLENET_RUNDIR);
    if (tuplenet_rundir == NULL) {
        tuplenet_rundir = TUPLENET_DEFAULT_RUN_PATH;
    }
    VLOG_INFO("tuplenet runtime dir:%s", tuplenet_rundir);

    char str_buf[MAX_STR_BUF_LEN];
    // create pipe fifo file to transmit message to tuplenet
    int n = snprintf(str_buf, MAX_STR_BUF_LEN, "%s/%s",
                     tuplenet_rundir, TUPLENET_PIPE_NAME);
    if (n < 0 || n >= MAX_STR_BUF_LEN) {
        VLOG_ERR("failed to write tuplenet rundir into str_buf");
        status = TP_STATUS_FAIL;
        goto exit;
    }

    tp_fifo_fd = create_fifo(str_buf);
    if (tp_fifo_fd == -1) {
        VLOG_ERR("failed to create fifo pipe");
        status = TP_STATUS_ERR_FIFO;
        goto exit;
    }
    VLOG_INFO("link to tuplenet success");

    const char *_ovs_rundir = getenv(OVS_RUNDIR);
    if (_ovs_rundir == NULL) {
        _ovs_rundir = ovs_rundir();
    }
    VLOG_INFO("ovs rundir:%s", _ovs_rundir);

    n = snprintf(str_buf, MAX_STR_BUF_LEN, "unix:%s/%s.mgmt",
                 _ovs_rundir, "br-int");
    if (n < 0 || n >= MAX_STR_BUF_LEN) {
        VLOG_ERR("failed to write ovs rundir into str_buf");
        status = TP_STATUS_FAIL;
        goto exit;
    }

    VLOG_INFO("target bridge:%s", str_buf);
    status = ovs_connect_br_mgmt(str_buf);
    if (status != TP_STATUS_OK) {
        VLOG_ERR("failed to connect the ovs bridge %s", str_buf);
        goto exit;
    }

exit:
    return status;
}

tp_status
run_controller()
{
    if (conn_seq_no != rconn_get_connection_seqno(swconn)) {
        tunnel_setup(swconn);
        conn_seq_no = rconn_get_connection_seqno(swconn);
        while(true) {
            struct ofpbuf *msg = rconn_recv(swconn);
            if (!msg) {
                rconn_run_wait(swconn);
                rconn_recv_wait(swconn);
                usleep(10 * 1000); /* sleep 10ms */
                continue;
            }
            const struct ofp_header *oh = msg->data;
            enum ofptype type;
            VLOG_INFO("controller receive msg");
            ofptype_decode(&type, oh);
            tunnel_recv(oh, type);
            ofpbuf_delete(msg);
        }
    } else {
        return TP_STATUS_FAIL;
    }

    return TP_STATUS_OK;

}

void
clean_env()
{
    if (tp_fifo_fd != -1) {
        close(tp_fifo_fd);
    }
}

int
main(int argc, char* argv[])
{
    tp_status status = init_log("pkt_controller");
    if (status != TP_STATUS_OK) {
        VLOG_ERR("exit because we cannot config log file");
        return status;
    }

    VLOG_INFO("Start pkt_controller");
    status = init_env();
    if (status != TP_STATUS_OK) {
        VLOG_ERR("failed to init env");
        goto exit;
    }

    status = run_controller();

exit:
    clean_env();
    VLOG_INFO("Exit pkt_controller");
    return status;
}

