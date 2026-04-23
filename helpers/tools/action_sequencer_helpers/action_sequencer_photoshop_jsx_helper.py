import os
from datetime import datetime
from config import BASE_PATH
from database.db_operation import ImageTeaDB


class PhotoshopJSXGenerator:
    def __init__(self):
        self.db = ImageTeaDB()
        self.jsx_dir = os.path.join(BASE_PATH, 'temp', 'jsx', 'photoshop')
        os.makedirs(self.jsx_dir, exist_ok=True)
    
    def _has_delay_actions(self, preset_steps):
        """Check if preset has any delay actions"""
        for step in preset_steps:
            action_detail = self.db.get_action_by_id(step['action_id'])
            if action_detail and action_detail.get('type') == 'Delay':
                return True
        return False
    
    def _split_steps_by_delay(self, preset_steps):
        """Split preset steps into segments separated by delays.
        
        Returns:
            List of tuples: [(steps_segment, delay_ms_after), ...]
            delay_ms_after is 0 for the last segment or if no delay follows
            
        Export steps are grouped with the preceding non-export segment to ensure
        they execute in the same JSX file. Segments with only export steps are
        merged with the previous segment.
        """
        segments = []
        current_segment = []
        pending_exports = []  # Buffer export steps until we have non-export steps
        
        for step in preset_steps:
            action_detail = self.db.get_action_by_id(step['action_id'])
            
            # Skip if action no longer exists (should be filtered earlier but be safe)
            if not action_detail:
                print(f"WARNING: Step references deleted action_id={step['action_id']}, skipping...")
                continue
                
            action_type = action_detail.get('type', 'Unknown')
            print(f"DEBUG: Processing step order={step['order_index']}, type={action_type}, name='{action_detail.get('name', '?')}'")
            
            if action_type == 'Delay':
                # Flush any pending exports to current segment before closing
                if pending_exports:
                    current_segment.extend(pending_exports)
                    pending_exports = []
                
                delay_ms = action_detail.get('delay', 0)
                if current_segment:
                    segments.append((current_segment, delay_ms))
                    current_segment = []
                elif segments:
                    # Merge consecutive delays
                    last_segment, last_delay = segments[-1]
                    segments[-1] = (last_segment, last_delay + delay_ms)
                else:
                    # Delay at start - create empty segment for timing purposes
                    segments.append(([], delay_ms))
            elif action_type == 'Export':
                # Buffer export steps
                pending_exports.append(step)
            else:
                # Non-export step (Action or Script) - flush pending exports first
                if pending_exports:
                    current_segment.extend(pending_exports)
                    pending_exports = []
                current_segment.append(step)
        
        # Flush remaining exports to current segment
        if pending_exports:
            current_segment.extend(pending_exports)
        
        if current_segment:
            segments.append((current_segment, 0))
        
        print(f"DEBUG: Split into {len(segments)} segments")
        for i, (seg, delay) in enumerate(segments):
            print(f"  Segment {i}: {len(seg)} steps, delay_after={delay}ms")
        
        return segments
    
    def generate_jsx(self, preset_id, source_files, output_path, config, is_single_run_with_file=False):
        """Generate JSX file untuk Photoshop
        
        Args:
            preset_id: ID preset dari database
            source_files: List file paths untuk diproses (bisa empty untuk single run)
            output_path: Path output folder
            config: Dict config (prefix, suffix, dll)
            is_single_run_with_file: True if single run mode with loaded file
        
        Returns:
            str: Path ke generated JSX file (jika tanpa delay)
            list: List of tuples [(jsx_path, delay_ms_after), ...] (jika ada delay)
        """
        preset_steps = self.db.get_preset_steps(preset_id)
        
        if not preset_steps:
            print(f"WARNING: No steps found for preset {preset_id}")
            return None
        
        # Filter out any steps that reference non-existent actions
        valid_steps = []
        for step in preset_steps:
            action_detail = self.db.get_action_by_id(step['action_id'])
            if action_detail:
                valid_steps.append(step)
            else:
                print(f"WARNING: Skipping step {step.get('order_index', '?')} - action_id={step['action_id']} no longer exists in database")
        
        if not valid_steps:
            print(f"ERROR: All steps in preset {preset_id} reference deleted/non-existent actions")
            return None
        
        is_batch = len(source_files) > 0 and not is_single_run_with_file
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Debug log step types
        step_types = []
        for s in valid_steps:
            action_detail = self.db.get_action_by_id(s['action_id'])
            step_types.append(action_detail.get('type', 'Unknown') if action_detail else 'Unknown')
        print(f"DEBUG: Generating JSX for preset {preset_id} with {len(valid_steps)} steps")
        print(f"DEBUG: Step types: {step_types}")
        print(f"DEBUG: is_batch={is_batch}, is_single_run_with_file={is_single_run_with_file}")
        print(f"DEBUG: source_files count: {len(source_files)}")
        
        if self._has_delay_actions(valid_steps):
            print(f"DEBUG: Has delay actions - using split JSX generation")
            return self._generate_split_jsx(preset_id, valid_steps, source_files, output_path, config, is_batch, is_single_run_with_file, timestamp)
        
        print(f"DEBUG: No delays - generating single JSX file")
        jsx_code = self._generate_jsx_code(valid_steps, source_files, output_path, config, is_batch, is_single_run_with_file)
        
        jsx_filename = f"preset_{preset_id}_{timestamp}.jsx"
        jsx_path = os.path.join(self.jsx_dir, jsx_filename)
        
        with open(jsx_path, 'w', encoding='utf-8') as f:
            f.write(jsx_code)
        
        print(f"Generated JSX: {jsx_path}")
        return jsx_path
    
    def _generate_split_jsx(self, preset_id, preset_steps, source_files, output_path, config, is_batch, is_single_run_with_file, timestamp):
        """Generate multiple JSX files split by delay actions.
        
        Returns:
            list: List of tuples [(jsx_path, delay_ms_after), ...]
        """
        split_dir = os.path.join(self.jsx_dir, f"preset_{preset_id}_{timestamp}_split")
        os.makedirs(split_dir, exist_ok=True)
        
        segments = self._split_steps_by_delay(preset_steps)
        result = []
        
        for idx, (segment_steps, delay_after) in enumerate(segments):
            # Handle empty segments - only skip if no delay OR this is not the first segment
            # Empty segment with delay at start should be preserved (represents initial delay)
            if not segment_steps and delay_after == 0:
                continue
            if not segment_steps and delay_after > 0:
                if result:
                    # Add delay to previous segment
                    last_path, last_delay = result[-1]
                    result[-1] = (last_path, last_delay + delay_after)
                # else: Skip standalone empty segment (no previous segment to add delay to)
                continue
            
            is_first_segment = (idx == 0)
            is_last_segment = (idx == len(segments) - 1)
            
            jsx_code = self._generate_segment_jsx_code(
                segment_steps, source_files, output_path, config, 
                is_batch, is_single_run_with_file,
                is_first_segment, is_last_segment
            )
            
            jsx_filename = f"segment_{idx:03d}.jsx"
            jsx_path = os.path.join(split_dir, jsx_filename)
            
            with open(jsx_path, 'w', encoding='utf-8') as f:
                f.write(jsx_code)
            
            print(f"Generated JSX segment {idx}: {jsx_path} (delay after: {delay_after}ms)")
            result.append((jsx_path, delay_after))
        
        return result
    
    def _generate_segment_jsx_code(self, segment_steps, source_files, output_path, config, 
                                    is_batch, is_single_run_with_file, is_first_segment, is_last_segment):
        """Generate JSX code for a segment (split by delay).
        
        For split mode:
        - First segment: opens documents
        - Middle segments: uses already open documents  
        - Last segment: closes documents
        """
        jsx = []
        jsx.append("// Generated by Image Tea - Action Sequencer (Segment)")
        jsx.append(f"// Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        jsx.append(f"// First segment: {is_first_segment}, Last segment: {is_last_segment}")
        jsx.append("")
        
        jsx.append("// Configuration")
        jsx.append("var config = {")
        jsx.append(f"    outputPath: '{output_path.replace(chr(92), '/')}',")
        jsx.append(f"    prefix: '{config.get('output_prefix', '')}',")
        jsx.append(f"    suffix: '{config.get('output_suffix', '')}',")
        jsx.append(f"    isBatch: {str(is_batch).lower()},")
        jsx.append(f"    isSingleRunWithFile: {str(is_single_run_with_file).lower()}")
        jsx.append("};")
        jsx.append("")
        
        jsx.append("function getUniqueFilePath(basePath) {")
        jsx.append("    var file = new File(basePath);")
        jsx.append("    if (!file.exists) return file;")
        jsx.append("    var folder = file.parent;")
        jsx.append("    var nameWithoutExt = file.name.replace(/\\.[^.]+$/, '');")
        jsx.append("    var ext = file.name.match(/\\.[^.]+$/)[0];")
        jsx.append("    for (var i = 1; i <= 999; i++) {")
        jsx.append("        var num = ('000' + i).slice(-3);")
        jsx.append("        var newFile = new File(folder + '/' + nameWithoutExt + '_' + num + ext);")
        jsx.append("        if (!newFile.exists) return newFile;")
        jsx.append("    }")
        jsx.append("    return file;")
        jsx.append("}")
        jsx.append("")
        
        for line in self._generate_safe_open_function():
            jsx.append(line)
        jsx.append("")
        
        if is_first_segment and (is_batch or is_single_run_with_file):
            jsx.append("// Source files")
            jsx.append("var sourceFiles = [")
            for sf in source_files:
                jsx.append(f"    '{sf.replace(chr(92), '/')}',")
            jsx.append("];")
            jsx.append("")
        
        export_steps = [s for s in segment_steps if self.db.get_action_by_id(s['action_id']).get('type') == 'Export']
        non_export_steps = [s for s in segment_steps if self.db.get_action_by_id(s['action_id']).get('type') != 'Export']
        
        jsx.append("// Main execution")
        jsx.append("try {")
        
        if is_batch:
            self._generate_batch_segment_code(jsx, non_export_steps, export_steps, is_first_segment, is_last_segment)
        elif is_single_run_with_file:
            self._generate_single_run_segment_code(jsx, non_export_steps, export_steps, is_first_segment, is_last_segment)
        else:
            self._generate_active_doc_segment_code(jsx, non_export_steps, export_steps, is_first_segment, is_last_segment)
        
        jsx.append("} catch(e) {")
        jsx.append("    alert('Error: ' + e.message);")
        jsx.append("}")
        
        return "\n".join(jsx)
    
    def _generate_batch_segment_code(self, jsx, non_export_steps, export_steps, is_first_segment, is_last_segment):
        """Generate batch processing code for a segment"""
        if is_first_segment:
            jsx.append("    for (var i = 0; i < sourceFiles.length; i++) {")
            jsx.append("        var doc = safeOpen(sourceFiles[i]);")
            jsx.append("        var originalFileName = doc.name.replace(/\\.[^.]+$/, '');")
        else:
            jsx.append("    var doc = app.activeDocument;")
            jsx.append("    var originalFileName = doc.name.replace(/\\.[^.]+$/, '');")
        jsx.append("")
        
        indent = "        " if is_first_segment else "    "
        
        for step in non_export_steps:
            action_detail = self.db.get_action_by_id(step['action_id'])
            if not action_detail:
                print(f"WARNING: Action not found for step {step.get('order_index', '?')}, skipping...")
                continue
            jsx.append(f"{indent}// Step {step['order_index']}: {step['name']}")
            action_type = action_detail.get('type', 'Action')
            if action_type == 'Action':
                jsx.append(f"{indent}app.doAction('{action_detail['name']}', '{step['action_set']}');")
            elif action_type == 'Script':
                js_code = action_detail.get('javascript_code', '').strip()
                if js_code:
                    for line in js_code.split('\n'):
                        jsx.append(f"{indent}{line}")
                else:
                    print(f"WARNING: Script action '{action_detail.get('name', '?')}' has no javascript_code, skipping...")
            jsx.append("")
        
        for step in export_steps:
            action_detail = self.db.get_action_by_id(step['action_id'])
            if action_detail:
                export_format = action_detail.get('export_format', 'PNG').upper()
                export_setting = action_detail.get('export_setting', 100)
                jsx.append(f"{indent}// Export: {action_detail['name']}")
                export_code = self._generate_export_code(export_format, indent, export_setting)
                for line in export_code.split('\n'):
                    jsx.append(line)
                jsx.append("")
        
        if is_last_segment:
            if is_first_segment:
                jsx.append("        doc.close(SaveOptions.DONOTSAVECHANGES);")
                jsx.append("    }")
            else:
                jsx.append("    doc.close(SaveOptions.DONOTSAVECHANGES);")
        elif is_first_segment:
            jsx.append("    }")
    
    def _generate_single_run_segment_code(self, jsx, non_export_steps, export_steps, is_first_segment, is_last_segment):
        """Generate single run with file code for a segment"""
        if is_first_segment:
            jsx.append("    if (sourceFiles.length > 0) {")
            jsx.append("        var doc = safeOpen(sourceFiles[0]);")
            jsx.append("        var originalFileName = doc.name.replace(/\\.[^.]+$/, '');")
            jsx.append("    }")
        else:
            jsx.append("    var doc = app.activeDocument;")
            jsx.append("    var originalFileName = doc.name.replace(/\\.[^.]+$/, '');")
        jsx.append("")
        
        for step in non_export_steps:
            action_detail = self.db.get_action_by_id(step['action_id'])
            if not action_detail:
                print(f"WARNING: Action not found for step {step.get('order_index', '?')}, skipping...")
                continue
            jsx.append(f"    // Step {step['order_index']}: {step['name']}")
            action_type = action_detail.get('type', 'Action')
            if action_type == 'Action':
                jsx.append(f"    app.doAction('{action_detail['name']}', '{step['action_set']}');")
            elif action_type == 'Script':
                js_code = action_detail.get('javascript_code', '').strip()
                if js_code:
                    for line in js_code.split('\n'):
                        jsx.append(f"    {line}")
                else:
                    print(f"WARNING: Script action '{action_detail.get('name', '?')}' has no javascript_code, skipping...")
            jsx.append("")
        
        for step in export_steps:
            action_detail = self.db.get_action_by_id(step['action_id'])
            if action_detail:
                export_format = action_detail.get('export_format', 'PNG').upper()
                export_setting = action_detail.get('export_setting', 100)
                jsx.append(f"    // Export: {action_detail['name']}")
                export_code = self._generate_export_code(export_format, "    ", export_setting)
                for line in export_code.split('\n'):
                    jsx.append(line)
                jsx.append("")
        
        if is_last_segment:
            jsx.append("    if (sourceFiles && sourceFiles.length > 0) {")
            jsx.append("        doc.close(SaveOptions.DONOTSAVECHANGES);")
            jsx.append("    }")
    
    def _generate_active_doc_segment_code(self, jsx, non_export_steps, export_steps, is_first_segment, is_last_segment):
        """Generate active document code for a segment (single run without source)"""
        has_content = bool(non_export_steps) or bool(export_steps)
        
        if is_first_segment:
            jsx.append("    if (app.documents.length == 0) {")
            jsx.append("        alert('No open document found. Please open a document.');")
            jsx.append("    } else {")
        
        jsx.append("        var doc = app.activeDocument;")
        jsx.append("        var originalFileName = doc.name.replace(/\\.[^.]+$/, '');")
        jsx.append("")
        
        for step in non_export_steps:
            action_detail = self.db.get_action_by_id(step['action_id'])
            if not action_detail:
                print(f"WARNING: Action not found for step {step.get('order_index', '?')}, skipping...")
                continue
            jsx.append(f"        // Step {step['order_index']}: {step['name']}")
            action_type = action_detail.get('type', 'Action')
            if action_type == 'Action':
                jsx.append(f"        app.doAction('{action_detail['name']}', '{step['action_set']}');")
            elif action_type == 'Script':
                js_code = action_detail.get('javascript_code', '').strip()
                if js_code:
                    for line in js_code.split('\n'):
                        jsx.append(f"        {line}")
                else:
                    print(f"WARNING: Script action '{action_detail.get('name', '?')}' has no javascript_code, skipping...")
            jsx.append("")
        
        for step in export_steps:
            action_detail = self.db.get_action_by_id(step['action_id'])
            if action_detail:
                export_format = action_detail.get('export_format', 'PNG').upper()
                export_setting = action_detail.get('export_setting', 100)
                jsx.append(f"        // Export: {action_detail['name']}")
                export_code = self._generate_export_code(export_format, "        ", export_setting)
                for line in export_code.split('\n'):
                    jsx.append(line)
                jsx.append("")
        
        # Only close the else block if we opened it AND we have content
        # If no content (no actions/steps defined), the alert already handles it
        if is_first_segment and has_content:
            jsx.append("    }")

    def _generate_jsx_code(self, preset_steps, source_files, output_path, config, is_batch, is_single_run_with_file):
        """Generate JSX code content"""
        
        jsx = []
        jsx.append("// Generated by Image Tea - Action Sequencer")
        jsx.append(f"// Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        jsx.append("")
        
        jsx.append("// Configuration")
        jsx.append("var config = {")
        jsx.append(f"    outputPath: '{output_path.replace(chr(92), '/')}',")
        jsx.append(f"    prefix: '{config.get('output_prefix', '')}',")
        jsx.append(f"    suffix: '{config.get('output_suffix', '')}',")
        jsx.append(f"    isBatch: {str(is_batch).lower()},")
        jsx.append(f"    isSingleRunWithFile: {str(is_single_run_with_file).lower()}")
        jsx.append("};")
        jsx.append("")
        
        jsx.append("function getUniqueFilePath(basePath) {")
        jsx.append("    var file = new File(basePath);")
        jsx.append("    if (!file.exists) return file;")
        jsx.append("    ")
        jsx.append("    var folder = file.parent;")
        jsx.append("    var nameWithoutExt = file.name.replace(/\\.[^.]+$/, '');")
        jsx.append("    var ext = file.name.match(/\\.[^.]+$/)[0];")
        jsx.append("    ")
        jsx.append("    for (var i = 1; i <= 999; i++) {")
        jsx.append("        var num = ('000' + i).slice(-3);")
        jsx.append("        var newFile = new File(folder + '/' + nameWithoutExt + '_' + num + ext);")
        jsx.append("        if (!newFile.exists) return newFile;")
        jsx.append("    }")
        jsx.append("    return file;")
        jsx.append("}")
        jsx.append("")
        
        for line in self._generate_safe_open_function():
            jsx.append(line)
        jsx.append("")
        
        if is_batch or is_single_run_with_file:
            jsx.append("// Source files")
            jsx.append("var sourceFiles = [")
            for sf in source_files:
                jsx.append(f"    '{sf.replace(chr(92), '/')}',")
            jsx.append("];")
            jsx.append("")
        
        export_steps = [s for s in preset_steps if self.db.get_action_by_id(s['action_id']).get('type') == 'Export']
        non_export_steps = [s for s in preset_steps if self.db.get_action_by_id(s['action_id']).get('type') != 'Export']
        
        jsx.append("// Main execution")
        jsx.append("try {")
        
        if is_batch:
            jsx.append("    for (var i = 0; i < sourceFiles.length; i++) {")
            jsx.append("        var doc = safeOpen(sourceFiles[i]);")
            jsx.append("        var originalFileName = doc.name.replace(/\\.[^.]+$/, '');")
            jsx.append("")
            jsx = self._add_steps_to_jsx(jsx, non_export_steps, export_steps, indent="        ")
            jsx.append("        doc.close(SaveOptions.DONOTSAVECHANGES);")
            jsx.append("    }")
        elif is_single_run_with_file:
            jsx.append("    if (sourceFiles.length > 0) {")
            jsx.append("        var doc = safeOpen(sourceFiles[0]);")
            jsx.append("        var originalFileName = doc.name.replace(/\\.[^.]+$/, '');")
            jsx.append("    }")
            jsx.append("")
            jsx = self._add_steps_to_jsx(jsx, non_export_steps, export_steps, indent="    ")
            jsx.append("    if (sourceFiles.length > 0) {")
            jsx.append("        doc.close(SaveOptions.DONOTSAVECHANGES);")
            jsx.append("    }")
        else:
            jsx.append("    if (app.documents.length == 0) {")
            jsx.append("        alert('No open document found. Please open a document first.');")
            jsx.append("    } else {")
            jsx.append("        var doc = app.activeDocument;")
            jsx.append("        var originalFileName = doc.name.replace(/\\.[^.]+$/, '');")
            jsx.append("")
            jsx = self._add_steps_to_jsx(jsx, non_export_steps, export_steps, indent="        ")
            jsx.append("    }")
        
        jsx.append("} catch(e) {")
        jsx.append("    alert('Error: ' + e.message);")
        jsx.append("}")
        
        return "\n".join(jsx)
    
    def _add_steps_to_jsx(self, jsx, non_export_steps, export_steps, indent="    "):
        """Helper to add steps (actions, scripts, exports) to JSX code"""
        for step in non_export_steps:
            action_detail = self.db.get_action_by_id(step['action_id'])
            if not action_detail:
                print(f"WARNING: Action not found for step {step.get('order_index', '?')}, skipping...")
                continue
            jsx.append(f"{indent}// Step {step['order_index']}: {step['name']}")
            
            action_type = action_detail.get('type', 'Action')
            
            if action_type == 'Action':
                jsx.append(f"{indent}app.doAction('{action_detail['name']}', '{step['action_set']}');")
            elif action_type == 'Delay':
                delay_ms = action_detail.get('delay', 0)
                if delay_ms > 0:
                    jsx.append(f"{indent}$.sleep({delay_ms});")
            elif action_type == 'Script':
                js_code = action_detail.get('javascript_code', '').strip()
                if js_code:
                    for line in js_code.split('\n'):
                        jsx.append(f"{indent}{line}")
                    delay_ms = action_detail.get('delay', 0)
                    if delay_ms > 0:
                        jsx.append(f"{indent}$.sleep({delay_ms});")
                else:
                    print(f"WARNING: Script action '{action_detail.get('name', '?')}' has no javascript_code, skipping...")
            
            jsx.append("")
        
        for step in export_steps:
            action_detail = self.db.get_action_by_id(step['action_id'])
            if action_detail:
                export_format = action_detail.get('export_format', 'PNG').upper()
                export_setting = action_detail.get('export_setting', 100)
                jsx.append(f"{indent}// Export: {action_detail['name']}")
                export_code = self._generate_export_code(export_format, indent, export_setting)
                for line in export_code.split('\n'):
                    jsx.append(line)
                jsx.append("")
        
        return jsx
    
    def _generate_safe_open_function(self):
        lines = []
        lines.append("function safeOpen(filePath) {")
        lines.append("    var f = new File(filePath);")
        lines.append("    if (!f.exists) throw new Error('File not found: ' + filePath);")
        lines.append("    var ext = f.name.match(/\\.([^.]+)$/);")
        lines.append("    ext = ext ? ext[1].toLowerCase() : '';")
        lines.append("    try {")
        lines.append("        switch(ext) {")
        lines.append("            case 'psd': return app.open(f, OpenDocumentType.PHOTOSHOP);")
        lines.append("            case 'psb': return app.open(f, OpenDocumentType.PHOTOSHOPLARGE);")
        lines.append("            case 'jpg': case 'jpeg': return app.open(f, OpenDocumentType.JPEG);")
        lines.append("            case 'png': return app.open(f, OpenDocumentType.PNG);")
        lines.append("            case 'tif': case 'tiff': return app.open(f, OpenDocumentType.TIFF);")
        lines.append("            case 'gif': return app.open(f, OpenDocumentType.GIF);")
        lines.append("            case 'bmp': return app.open(f, OpenDocumentType.BMP);")
        lines.append("            case 'pdf': return app.open(f, OpenDocumentType.PDF);")
        lines.append("            case 'eps': case 'epsf': return app.open(f, OpenDocumentType.EPS);")
        lines.append("            case 'ai': return app.open(f, OpenDocumentType.EPS);")
        lines.append("            case 'raw': case 'cr2': case 'nef': case 'arw': case 'dng':")
        lines.append("                return app.open(f, OpenDocumentType.CAMERARAW);")
        lines.append("            default: return app.open(f);")
        lines.append("        }")
        lines.append("    } catch(e) {")
        lines.append("        return app.open(f);")
        lines.append("    }")
        lines.append("}")
        return lines

    def _generate_export_code(self, export_format, indent, export_setting=100):
        """Generate export code for Photoshop
        
        Handles multiple exports by ensuring proper document state reset between exports.
        """
        code_lines = []
        
        # Add reset/flatten for document before export to handle multiple exports
        code_lines.append(f"{indent}// Reset document state before export")
        code_lines.append(f"{indent}app.activeDocument.flatten();")
        code_lines.append("")
        
        if export_format == 'PNG':
            code_lines.append(f"{indent}var pngOptions = new ExportOptionsSaveForWeb();")
            code_lines.append(f"{indent}pngOptions.format = SaveDocumentType.PNG;")
            code_lines.append(f"{indent}pngOptions.PNG8 = false;")
            code_lines.append(f"{indent}var basePath = config.outputPath + '/' + config.prefix + originalFileName + config.suffix + '.png';")
            code_lines.append(f"{indent}var saveFile = getUniqueFilePath(basePath);")
            code_lines.append(f"{indent}doc.exportDocument(saveFile, ExportType.SAVEFORWEB, pngOptions);")
        elif export_format == 'JPG' or export_format == 'JPEG':
            quality = int((export_setting / 100) * 12)
            if quality < 1:
                quality = 1
            elif quality > 12:
                quality = 12
            code_lines.append(f"{indent}var jpgOptions = new JPEGSaveOptions();")
            code_lines.append(f"{indent}jpgOptions.quality = {quality};")
            code_lines.append(f"{indent}var basePath = config.outputPath + '/' + config.prefix + originalFileName + config.suffix + '.jpg';")
            code_lines.append(f"{indent}var saveFile = getUniqueFilePath(basePath);")
            code_lines.append(f"{indent}doc.saveAs(saveFile, jpgOptions, true);")
        elif export_format == 'PSD':
            code_lines.append(f"{indent}var psdOptions = new PhotoshopSaveOptions();")
            code_lines.append(f"{indent}psdOptions.embedColorProfile = true;")
            code_lines.append(f"{indent}var basePath = config.outputPath + '/' + config.prefix + originalFileName + config.suffix + '.psd';")
            code_lines.append(f"{indent}var saveFile = getUniqueFilePath(basePath);")
            code_lines.append(f"{indent}doc.saveAs(saveFile, psdOptions, true);")
        elif export_format == 'PDF':
            code_lines.append(f"{indent}var pdfOptions = new PDFSaveOptions();")
            code_lines.append(f"{indent}var basePath = config.outputPath + '/' + config.prefix + originalFileName + config.suffix + '.pdf';")
            code_lines.append(f"{indent}var saveFile = getUniqueFilePath(basePath);")
            code_lines.append(f"{indent}doc.saveAs(saveFile, pdfOptions, true);")
        elif export_format == 'EPS':
            code_lines.append(f"{indent}var epsOptions = new EPSSaveOptions();")
            code_lines.append(f"{indent}epsOptions.encoding = SaveEncoding.BINARY;")
            code_lines.append(f"{indent}epsOptions.embedColorProfile = true;")
            code_lines.append(f"{indent}var basePath = config.outputPath + '/' + config.prefix + originalFileName + config.suffix + '.eps';")
            code_lines.append(f"{indent}var saveFile = getUniqueFilePath(basePath);")
            code_lines.append(f"{indent}doc.saveAs(saveFile, epsOptions, true);")
        elif export_format == 'TIFF':
            code_lines.append(f"{indent}var tiffOptions = new TiffSaveOptions();")
            code_lines.append(f"{indent}var basePath = config.outputPath + '/' + config.prefix + originalFileName + config.suffix + '.tif';")
            code_lines.append(f"{indent}var saveFile = getUniqueFilePath(basePath);")
            code_lines.append(f"{indent}doc.saveAs(saveFile, tiffOptions, true);")  
        
        return "\n".join(code_lines)
