#ifdef HAVE_CONFIG_H
#include "config.h"
#endif

#if HAVE_OPENVSWITCH_RCONN_H
#include "openvswitch/rconn.h"
#else
// rconn_* functions were not public in old version of ovs
// need to declare those function to avoid warning
struct rconn *rconn_create(int inactivity_probe_interval,
                           int max_backoff, uint8_t dscp,
                           uint32_t allowed_versions);

struct rconn_packet_counter;
int rconn_send(struct rconn *, struct ofpbuf *, struct rconn_packet_counter *);
int rconn_get_version(const struct rconn *);
void rconn_connect(struct rconn *, const char *target, const char *name);
void rconn_run(struct rconn *);
bool rconn_is_connected(const struct rconn *);
unsigned int rconn_get_connection_seqno(const struct rconn *);
struct ofpbuf *rconn_recv(struct rconn *);
void rconn_run_wait(struct rconn *);
void rconn_recv_wait(struct rconn *);
#endif

const char *ovs_rundir(void);
