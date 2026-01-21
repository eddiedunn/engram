# Engram Deployment Guide

This guide covers deploying Engram to GPU-enabled infrastructure using Ansible with Quadlet (systemd-managed containers).

## Prerequisites

### Infrastructure
- GPU server with NVIDIA GPU and drivers installed
- Tailscale mesh network configured
- Step CA instance for TLS certificates
- Ansible control node with access to target server

### Required Components
- NVIDIA Container Toolkit installed on host
- CDI (Container Device Interface) configured
- Podman with systemd integration (Quadlet)
- Caddy reverse proxy (deployed via `caddy_gpu_dev` role)

## Deployment Steps

### 1. Configure Secrets

Store credentials securely in gopass:

```bash
# Database password
gopass insert engram/db-password

# API key for authentication
gopass insert engram/api-key
```

### 2. Configure Group Variables

In `your-infra/group_vars/engram_vps.yml`:

```yaml
engram_db_password: "{{ lookup('community.general.gopass', 'engram/db-password') }}"
engram_api_key: "{{ lookup('community.general.gopass', 'engram/api-key') }}"

# Optional overrides
engram_embedding_model: "BAAI/bge-large-en-v1.5"
engram_log_level: "INFO"
engram_gpu_enabled: true
```

### 3. Deploy Infrastructure

From `your-infra` directory:

```bash
# Deploy Engram service
ansible-playbook -i inventory/hosts.yml playbooks/deploy-engram.yml

# Deploy Caddy reverse proxy
ansible-playbook -i inventory/hosts.yml playbooks/deploy-caddy-gpu.yml
```

### 4. Verify Deployment

Check service status:

```bash
# On target server
systemctl --user status engram-app.service
systemctl --user status engram-db.service
systemctl --user status caddy-gpu.service

# Check logs
journalctl --user -u engram-app.service -f
```

Test endpoint:

```bash
# Health check (direct)
curl http://localhost:8800/health

# Via Caddy (requires valid cert)
curl https://engram.your-domain.example.com/health
```

## Caddy Configuration

Caddy acts as a reverse proxy with automatic TLS:

```
engram.your-domain.example.com {
    reverse_proxy localhost:8800

    tls {
        ca https://your-ca.example.com:9000/acme/acme/directory
    }
}
```

### Certificate Renewal

Caddy automatically:
1. Obtains certificates from Step CA via ACME
2. Renews certificates before expiration
3. Reloads configuration without downtime

No manual intervention required for certificate lifecycle.

## Container Architecture

### Network Setup
- Internal network: `10.x.x.0/24`
- Database IP: `10.x.x.10`
- App IP: `10.x.x.11`
- External access: Caddy on host network

### GPU Passthrough
- Uses CDI for NVIDIA GPU access
- Configured via `--device nvidia.com/gpu=all`
- Requires nvidia-container-toolkit on host

### Resource Limits
- **Engram App**: 8GB RAM, 4 CPU cores (GPU workload)
- **PostgreSQL**: 2GB RAM, 2 CPU cores
- **Caddy**: 256MB RAM, 1 CPU core

## Troubleshooting

### GPU Not Available

Check NVIDIA container toolkit:
```bash
which nvidia-ctk
nvidia-ctk cdi list
ls -la /etc/cdi/nvidia.yaml
```

Generate CDI config if missing:
```bash
sudo nvidia-ctk cdi generate --output=/etc/cdi/nvidia.yaml
```

### Database Connection Issues

Verify network and credentials:
```bash
podman exec engram-app env | grep DATABASE_URL
podman exec engram-db psql -U engram -c '\l'
```

### Certificate Errors

Check Step CA connectivity:
```bash
curl -k https://your-ca.example.com:9000/health
```

View Caddy logs:
```bash
journalctl --user -u caddy-gpu.service -f
```

### Service Won't Start

Check Quadlet configuration:
```bash
# View generated unit files
ls -la ~/.config/containers/systemd/

# Check for errors
systemctl --user daemon-reload
systemctl --user status engram-app.service
journalctl --user -u engram-app.service -n 50
```

## Updating Engram

### Application Updates

1. Build new image with updated version tag
2. Update `engram_version` in group_vars
3. Re-run deployment playbook:

```bash
ansible-playbook -i inventory/hosts.yml playbooks/deploy-engram.yml
```

Quadlet will pull the new image and restart services.

### Database Migrations

Migrations run automatically on startup via Alembic:

```bash
# Check migration status
podman exec engram-app alembic current
podman exec engram-app alembic history
```

## Monitoring

### Health Checks
- Endpoint: `http://localhost:8800/health`
- Interval: 30s
- Start period: 60s (allows model download)

### Logs
```bash
# Application logs
journalctl --user -u engram-app.service -f

# Database logs
journalctl --user -u engram-db.service -f

# Caddy logs
journalctl --user -u caddy-gpu.service -f
```

### Resource Usage
```bash
podman stats engram-app engram-db caddy-gpu
nvidia-smi  # GPU utilization
```

## Configuration Reference

See `your-infra/roles/engram_dev/defaults/main.yml` for all available configuration options.

Key settings:
- `engram_embedding_model`: HuggingFace model name
- `engram_gpu_enabled`: Enable/disable GPU passthrough
- `engram_port`: Application port (default: 8800)
- `engram_workers`: Uvicorn worker count
- `engram_db_shared_buffers`: PostgreSQL memory tuning
