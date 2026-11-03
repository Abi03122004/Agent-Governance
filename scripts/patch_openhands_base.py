"""Patch OpenHands base.py to prevent unmediated fallthrough and govern MCPAction."""

from pathlib import Path

base_file = Path("external/OpenHands/openhands/runtime/base.py")
content = base_file.read_text(encoding="utf-8")
norm_content = content.replace("\r\n", "\n")

target_run_action = """                    if decision.action_id and decision.execution_authorization:
                        out_content = getattr(obs, 'content', str(obs)) if obs else ''
                        gov_client.report_result(
                            action_id=decision.action_id,
                            execution_authorization=decision.execution_authorization,
                            status=exec_status,
                            output={'observation': out_content[:2048]},
                        )

        observation = getattr(self, action_type)(action)
        return observation"""

replacement_run_action = """                    if decision.action_id and decision.execution_authorization:
                        out_content = getattr(obs, 'content', str(obs)) if obs else ''
                        gov_client.report_result(
                            action_id=decision.action_id,
                            execution_authorization=decision.execution_authorization,
                            status=exec_status,
                            output={'observation': out_content[:2048]},
                        )
            else:
                return ErrorObservation(
                    content=f'Governance Policy Rejected Action: {decision.explanation or "Action not allowed"}',
                    error_id=decision.reason_code or 'GOVERNANCE_BLOCKED',
                )

        observation = getattr(self, action_type)(action)
        return observation"""

target_mcp = """            if isinstance(event, MCPAction):
                observation: Observation = await self.call_tool_mcp(event)
            else:
                observation = await call_sync_from_async(self.run_action, event)"""

replacement_mcp = """            if isinstance(event, MCPAction):
                gov_client = getattr(self, '_governance_client', None)
                if gov_client is None:
                    try:
                        from openhands.runtime.governance_client import get_governance_client
                        gov_client = get_governance_client()
                        self._governance_client = gov_client
                    except Exception:
                        gov_client = None

                if gov_client and gov_client.is_configured and gov_client.is_governed_action(event):
                    decision = await call_sync_from_async(gov_client.mediate, event)
                    if decision.decision == 'BLOCK':
                        observation = ErrorObservation(
                            content=f'Governance Policy Blocked Action [{decision.reason_code}]: {decision.explanation}',
                            error_id=decision.reason_code,
                        )
                    elif decision.decision == 'SUSPEND':
                        if hasattr(self, 'close'):
                            try:
                                self.close()
                            except Exception:
                                pass
                        observation = ErrorObservation(
                            content=f'Governance Security TRIPWIRE: Agent SUSPENDED. Action halted: {decision.explanation}',
                            error_id='AGENT_SUSPENDED',
                        )
                    elif decision.decision == 'ALLOW':
                        obs = None
                        exec_status = 'succeeded'
                        try:
                            obs = await self.call_tool_mcp(event)
                            if isinstance(obs, ErrorObservation):
                                exec_status = 'failed'
                            observation = obs
                        except Exception as exc:
                            exec_status = 'failed'
                            observation = ErrorObservation(f'MCP Tool execution failed: {str(exc)}')
                        finally:
                            if decision.action_id and decision.execution_authorization:
                                out_content = getattr(obs, 'content', str(obs)) if obs else ''
                                await call_sync_from_async(
                                    gov_client.report_result,
                                    action_id=decision.action_id,
                                    execution_authorization=decision.execution_authorization,
                                    status=exec_status,
                                    output={'observation': out_content[:2048]},
                                )
                    else:
                        observation = ErrorObservation(
                            content=f'Governance Policy Rejected Action: {decision.explanation or "Action not allowed"}',
                            error_id=decision.reason_code or 'GOVERNANCE_BLOCKED',
                        )
                else:
                    observation = await self.call_tool_mcp(event)
            else:
                observation = await call_sync_from_async(self.run_action, event)"""

if target_run_action not in norm_content:
    print("Warning: target_run_action not found in base.py")
else:
    norm_content = norm_content.replace(target_run_action, replacement_run_action, 1)
    print("Replaced run_action block")

if target_mcp not in norm_content:
    print("Warning: target_mcp not found in base.py")
else:
    norm_content = norm_content.replace(target_mcp, replacement_mcp, 1)
    print("Replaced MCP block")

with open(base_file, "w", encoding="utf-8", newline="\r\n") as f:
    f.write(norm_content)

print("Finished updating base.py")

client_src = Path(__file__).resolve().parent / "openhands_runtime_governance_client.py"
client_dst = Path("external/OpenHands/openhands/runtime/governance_client.py")
if client_src.exists() and client_dst.parent.exists():
    client_dst.write_text(client_src.read_text(encoding="utf-8"), encoding="utf-8")
    print(f"Copied {client_src.name} to {client_dst}")


