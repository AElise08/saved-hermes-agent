# Saved: a Plow Chat Hermes agent that archives ideas to Notion and texts
# three this-week picks every Sunday.
#
# Pinned by digest, same pattern as plow-pbc/life-assistant-hermes-agent:
# a moving tag would substitute unreviewed code under a live credential.
FROM public.ecr.aws/e1h7x4a2/plow-cloud-agents:base-ef0019372ff8bca593611b31ebd2e08f9f1458ff@sha256:a8a2f97ad78b8192d80a984dce81d3bf5a9a883d18cb7b677704913a09b56aee

COPY runtime/SOUL.md /var/lib/hermes/SOUL.md
COPY LICENSE NOTICE /usr/share/doc/saved/

# Bundled skill: the base runtime reconciles /opt/hermes/skills into the home.
COPY skills/saved/ /opt/hermes/skills/saved/

RUN find /opt/hermes/skills -mindepth 1 -type d -exec chmod 0755 {} + \
 && find /opt/hermes/skills -mindepth 1 -type f ! -perm -u+x -exec chmod 0644 {} + \
 && find /opt/hermes/skills -mindepth 1 -type f -perm -u+x -exec chmod 0755 {} + \
 && chmod 0644 /var/lib/hermes/SOUL.md

# Root-owned scripts the Sunday drain runs. The home copy is what the agent
# reads during a turn; scheduling that copy would run whatever a turn last
# wrote, unattended, with the chat credential.
COPY scripts/ /opt/saved/scripts/
COPY templates/ /opt/saved/templates/
RUN chown -R root:root /opt/saved \
 && find /opt/saved -type d -exec chmod 0755 {} + \
 && find /opt/saved -type f -exec chmod 0644 {} + \
 && chmod 0755 /opt/saved/scripts/*.py

COPY image/s6-overlay/ /etc/s6-overlay/
COPY --chmod=0755 image/cont-init.d/20-saved-seed /etc/cont-init.d/20-saved-seed
