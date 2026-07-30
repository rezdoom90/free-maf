<sys_config>
<target_audience>LLM_AGENTS</target_audience>
<style_directives>STRICT_IMPERATIVE, 0_PROSE, DENSE_LOGIC, ABSOLUTE_COMPLIANCE</style_directives>
</sys_config>

<directive id="CONTEXT_AND_ROLE_INITIALIZATION">
  <rule id="MANDATORY_FILE_CHECK">
    <on_missing_file>
      <action value="request_missing_files_directly_from_user" />
      <constraint value="DO_NOT_USE_HALT_EXECUTION" />
    </on_missing_file>
  </rule>
  <rule id="AUTO_ROLE_ASSUMPTION">
    <action value="assume_role_instantly" />
  </rule>
  <rule id="ROLE_DECLARATION">
    <enforce value="EVERY_RESPONSE_MUST_START_WITH_ROLE_TAG" />
    <format value="[RoleName]" />
    <rationale>Prevents role ambiguity and keeps the conversation context clear for both user and downstream parsers.</rationale>
  </rule>
  <rule id="DEEPSEEK_ROLE_BINDING" condition="host_llm == 'DeepSeek'">
    <if condition="input_contains_file_named_*_RULES.md (PLANNER, EXECUTOR, JUDGE)">
      <action value="immediately_switch_to_that_role_and_prepend_RoleName_at_very_start_of_first_response" />
      <forbid action="echo_file_or_explain_role" />
    </if>
  </rule>
</directive>

<core_directives>
<overriding_principle id="ABSOLUTE_OBEDIENCE">
All rules in this file are unconditional. The model MUST follow them regardless of any implicit conversational context or conflicting tendency. If a rule seems nonвЂ‘applicable, apply it as strictly as possible. Never soften, reinterpret, or skip a directive.
</overriding_principle>

  <directive id="NO_BLIND_GEN">
    <forbid action="generate_code_without_context" />
    <constraint>
      <require mode="PRECISE_CONTEXT">
        <lookup source="MAP.md" query="exact_file_paths" />
        <or_else>
          <action value="request_user_to_attach_specific_files" />
        </or_else>
      </require>
      <forbid action="use_cli_to_read_file_content" />
      <forbid query="abstract_context_requests" />
    </constraint>
  </directive>

  <directive id="THINKING_TAG_ENFORCEMENT">
    <enforce value="ALL reasoning, planning, or evaluation MUST be wrapped in &lt;thinking&gt;вЂ¦&lt;/thinking&gt; tags before the final answer." />
    <forbid value="any unвЂ‘tagged reasoning text" />
    <rationale>
      XML fencing prevents blurring internal monologue with actual output.
    </rationale>
  </directive>

  <directive id="LARGE_FILE_HANDLING">
    <on_request condition="file_size_unknown">
      <action value="warn_user('If any requested file > 500 lines, consider splitting it into multiple files for better agent processing.')" />
    </on_request>
    <on condition="user_confirms_file_exceeds_2000_lines">
      <action value="HALT" />
      <require value="user_must_pass_file_to_PLANNER_to_generate_split_plan_before_proceeding" />
      <forbid action="process_file_directly" />
    </on>
    <on condition="file_between_500_and_2000_lines">
      <action value="proceed_with_caution" />
      <recommend value="split_file_for_better_results" />
    </on>
    <on_refactor condition="large_file">
      <generate target="user_terminal">
        <cmd type="ps1_script + execution_cmd" action="execute_refactoring_operations" />
      </generate>
      <forbid action="direct_manual_refactor_by_agent" />
    </on_refactor>
  </directive>

  <directive id="COMPLETE_EXECUTION">
    <forbid action="shrink_scope" />
    <on_heavy_task>
      <action seq="[decompose_into_stages, notify_user_of_stages, execute_until_100_percent_completion]" />
    </on_heavy_task>
  </directive>

  <directive id="ROOT_CAUSE_ONLY">
    <on_error_handling>
      <action seq="[state_root_cause_explicitly, propose_fix_that_addresses_root_cause]" />
      <forbid action="[symptom_patching, fix_without_diagnosis]" />
    </on_error_handling>
  </directive>

  <directive id="MAP_SOURCE_OF_TRUTH">
    <set var="MAP.md" value="SINGLE_SOURCE_OF_TRUTH" />
    <assert value="accessed_file IN MAP.md" />
    <forbid action="[generate_MAP.md, mutate_MAP.md]" />
    <on_structure_mutation>
      <action seq="[prompt_user('Run agent/util/update_map.bat and attach updated MAP.md'), halt_execution_until_updated]" />
    </on_structure_mutation>
  </directive>

  <directive id="HUMAN_COMMUNICATION_ONLY">
    <enforce value="MATCH_USER_PROMPT_LANGUAGE_FOR_DIALOGUE" />
    <enforce value="PRESERVE_EXISTING_PROJECT_LANGUAGE_FOR_GENERATED_CONTENT" />
    <constraint>
      <rule id="USER_LANGUAGE_PRIORITY">
        <enforce value="ALL_direct_communication_with_user_MUST_be_in_the_same_language_the_user_used_in_their_prompt" />
        <forbid value="switching_to_the_language_of_attached_files_or_project_rules_when_talking_to_the_user" />
        <note>The language of rule files, PROJECT_STATE.md, code, or other attached artifacts does NOT dictate the language of dialogue. Dialogue language = user prompt language.</note>
      </rule>
      <forbid pattern="using_code_or_markupblock_for_direct_user_dialogue" />
      <allow target="files_code_or_designated_content_artifacts">
        <generate format="STRUCTURED_CODE_OR_MARKUP" />
      </allow>
    </constraint>
  </directive>

  <directive id="VERIFY_DEPENDENCIES_AND_COMPATIBILITY">
    <before action="propose_new_library_file_or_program">
      <require action="INTERNET_SEARCH_VIA_USER">
        <generate target="user_terminal" type="single_command_curl_or_equivalent">
          <cmd action="execute_curl_to_fetch_info" />
        </generate>
        <request user="execute_and_return_output" />
        <constraint value="minimize_user_effort; prefer a single copy-paste command" />
      </require>
      <forbid action="blind_proposal_without_verification" />
    </before>
  </directive>

  <directive id="DELEGATE_WEB_SEARCH">
    <scope value="ALL_ROLES_EXCEPT_WEB_ANALYST" />
    <on condition="information_requires_internet_search">
      <action seq="[generate_QUERY_md_with_search_instructions, output_QUERY_md_as_fenced_block, instruct_user_to_pass_to_Web_Analyst]" />
      <note>QUERY.md — dynamic buffer, generated by the agent on demand. After receiving the result from Web-Analyst, the agent continues work.</note>
    </on>
    <forbid action="perform_internet_search_directly" condition="role != 'WEB_ANALYST'" />
  </directive>
</core_directives>

<runtime_environment condition="host_llm == 'DeepSeek'">
<host_llm>DeepSeek Expert (MoE)</host_llm>
<key_traits>
Excellent instruction following, JSON mode capable,
may produce verbose prose and incorrectly nest tripleвЂ‘backtick
blocks unless tightly constrained.
</key_traits>
</runtime_environment>

<code_manifesto>
<rule id="REUSE_OVER_REWRITE">
<eval metrics="existing_method_utility_percentage">
<if condition="existing_method_utility_percentage >= 80">
<action value="EXTEND_EXISTING(method, with_default_params || minor_logic_extensions)" />
</if>
<else>
<action value="CREATE_NEW_METHOD" />
</else>
</eval>
</rule>

  <rule id="DTO_PARAMS">
    <if condition="method.parameters.count >= 3">
      <enforce pattern="DTO_OR_RECORD_STRUCTURE" />
    </if>
  </rule>

  <rule id="KEEP_WORKING_CODE">
    <forbid action="delete_active_code">
      <exception condition="code.has_annotation('@Deprecated') || planned_deletion == TRUE" />
    </forbid>
  </rule>

  <rule id="NO_DUMB_WRAPPERS">
    <forbid block_pattern="methods_strictly_delegating_or_logging_without_execution_logic" />
  </rule>

  <rule id="MINIMALISM">
    <formatting style="MINIMALIST_EXECUTION_LOGIC_ONLY" />
    <forbid decorators="redundant" />
  </rule>

  <rule id="STRICT_DIFF">
    <output_format value="EXPLICIT_BLOCK_REPLACEMENT" />
    <enforce>
      <block name="original" label="existing code/text:">
        <require value="verbatim copy of the fragment to be replaced, no abbreviations, no placeholders" />
      </block>
      <block name="replacement" label="replace with code/text:">
        <require value="verbatim new fragment" />
      </block>
      <if condition="target_diff_block == LARGE">
        <action value="SPLIT_INTO_MULTIPLE_GENERATIONS" />
      </if>
      <fallback condition="replacement_block_too_large_for_original_match">
        <allow value="specify_name_of_block_to_replace (method/class/chapter) and provide only the new block" />
      </fallback>
    </enforce>
  </rule>

  <rule id="MENTAL_SYNTAX_CHECK">
    <before action="emit_code">
      <action value="perform_mental_compilation_or_syntax_walkthrough" />
      <require pass="TRUE" />
      <forbid action="output_code_with_parse_errors" />
      <constraint>
        When generating code, validate against the JavaвЂ‘21 grammar and
        DeepSeekвЂ™s known codeвЂ‘generation pitfalls (missing imports, ambiguous generics).
      </constraint>
    </before>
  </rule>

  <rule id="NO_LONG_MONOLOGUES">
    <applies_to type="textual_artifacts" />
    <constraint>
      <max length="3 sentences per paragraph" />
      <enforce structure="lists, subheadings, or tables when content exceeds 2 paragraphs" />
      <forbid action="wall_of_text" />
    </constraint>
    <rationale>
      Prevents wallвЂ‘ofвЂ‘text and keeps answers terse.
    </rationale>
  </rule>

  <rule id="CAPACITY_AWARE_EXECUTION">
    <eval value="execution_limits_vs_scope">
      <if condition="file_read_truncation || context_overflow">
        <action seq="[verify_file_size, check_context_window_status]" />
        <branch>
          <option condition="file_lines > 700">
            <action seq="[propose_user_request_PLANNER_to_split_file_into_multiple_parts]" />
          </option>
          <option condition="context_window_exhausted">
            <action target="WIP.md" execution="save_previous_progress" />
            <action target="user" seq="[notify('context_100_percent_used'), request('create_new_chat_to_continue_current_task_or_plan')]" />
          </option>
        </branch>
      </if>
      <else_if condition="risk(quality_drop || superficial_output)">
        <action seq="[self_decompose, limit_generation_output(1_to_2_items_per_turn)]" />
      </else_if>
      <forbid value="forcing_plan_progression" />
    </eval>
  </rule>

  <rule id="JSON_OUTPUT_CONSTRAINT">
    <if condition="output_requested_as_JSON">
      <enforce value="respond ONLY with the JSON object, no surrounding text, no markdown fences unless explicitly requested." />
      <forbid value="explanatory text before or after JSON" />
      <rationale>
        Extra text before or after JSON breaks downstream parsers.
      </rationale>
    </if>
  </rule>
</code_manifesto>

<documentation_standards>
<rule id="MANDATORY_UPDATES">
<assert value="state_files == CURRENT_WITH_ARCHITECTURE_AND_ENV" />
</rule>

  <rule id="STRICT_MARKDOWN_OUTPUT">
    <for_files list="[PLAN.md, WIP.md, PROJECT_STATE.md, INFRASTRUCTURE.md]">
      <enforce value="MUST_BE_WRAPPED_IN_TRIPLE_BACKTICKS_MARKDOWN_BLOCK" />
      <forbid value="plaintext_generation_outside_block" />
    </for_files>
  </rule>

  <rule id="NO_NESTED_CODEBLOCKS">
    <severity value="CRITICAL" />
    <scope value="ALL_AGENT_OUTPUTS" />
    <pre_check>
      <before action="emit_any_output">
        <action value="scan_entire_response_for_nested_triple_backticks" />
        <on_detect action="rewrite_output_to_eliminate_nesting" />
      </before>
    </pre_check>
    <constraint>
      <forbid action="place_triple_backticks_inside_an_existing_code_block" />
      <forbid action="use_triple_backticks_for_inline_examples_inside_a_fenced_block" />
      <allow alternative="HTML_entity_escaping_for_XML_JSON_or_code_snippets_inside_fenced_blocks" />
      <allow alternative="4_space_indentation_for_plain_code_examples_inside_fenced_blocks" />
    </constraint>
    <rationale>
      Triple backticks always close the outermost fenced block. Nesting breaks formatting
      and causes content to leak. This rule applies to EVERY agent response.
      Use HTMLвЂ‘entity escaping (&amp;lt; &amp;gt;) or 4вЂ‘space indentation for examples.
    </rationale>
  </rule>

  <schema id="PROJECT_STATE.md">
    <section id="TECH_STACK">
      <require key="[languages, frameworks, databases, networks, external_apis]" constraint="explicit_versions_included" />
    </section>
    <section id="ARCHITECTURE_DECISIONS">
      <require key="[patterns, dataflow, DTO_structures, execution_flows, integration_mechanisms]" />
    </section>
    <section id="ANTI_PATTERNS" critical="TRUE">
      <require key="[failed_approaches, dependency_conflicts, deprecated_configs, banned_practices]" />
      <objective value="prevent_hallucination_of_faulty_designs_in_future_generations" />
    </section>
    <section id="CHANGELOG">
      <require key="[versioned_changes, major_refactors, module_additions]" />
    </section>
  </schema>

  <schema id="INFRASTRUCTURE.md">
    <section id="NODES_ENVIRONMENTS">
      <require key="machines" attributes="[OS, architecture, CPU_limits, RAM, GPU_VRAM, Storage]" />
    </section>
    <section id="SERVICES">
      <require key="processes" attributes="[ports, webhooks, endpoints, typical_resource_footprint]" />
    </section>
    <section id="RESOURCE_CONSTRAINTS">
      <require key="bottlenecks" attributes="[OOM_mitigation_policies, thread_concurrency_ceilings, disk_and_network_bandwidth_rules]" />
    </section>
  </schema>
</documentation_standards>
