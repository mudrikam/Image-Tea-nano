import os
import json
import time
from datetime import datetime
from config import BASE_PATH
from database.db_operation import ImageTeaDB


class IllustratorJSXGenerator:
    def __init__(self, exec_path=None):
        self.db = ImageTeaDB()
        self.exec_path = exec_path
        self.jsx_dir = os.path.join(BASE_PATH, 'temp', 'jsx', 'illustrator')
        self.temp_dir = os.path.join(BASE_PATH, 'temp', 'illustrator_resident')
        os.makedirs(self.jsx_dir, exist_ok=True)
        os.makedirs(self.temp_dir, exist_ok=True)
        self.heartbeat_file = os.path.join(self.temp_dir, 'heartbeat.txt')
        self.command_file = os.path.join(self.temp_dir, 'command.json')
        self.resident_jsx = os.path.join(self.jsx_dir, 'ImageTea_Resident.jsx')
        
        # EPS version mapping: index -> Compatibility constant
        self.eps_version_map = {
            0: 'Compatibility.ILLUSTRATOR24',
            1: 'Compatibility.ILLUSTRATOR19',
            2: 'Compatibility.ILLUSTRATOR16',
            3: 'Compatibility.ILLUSTRATOR15',
            4: 'Compatibility.ILLUSTRATOR14',
            5: 'Compatibility.ILLUSTRATOR13',
            6: 'Compatibility.ILLUSTRATOR12',
            7: 'Compatibility.ILLUSTRATOR11',
            8: 'Compatibility.ILLUSTRATOR10',
            9: 'Compatibility.ILLUSTRATOR9',
            10: 'Compatibility.ILLUSTRATOR8',
            11: 'Compatibility.ILLUSTRATOR3',
            12: 'Compatibility.JAPANESEILLUSTRATOR3'
        }
    
    def is_resident_alive(self):
        """Check if resident script is running by checking heartbeat"""
        if not os.path.exists(self.heartbeat_file):
            return False
        
        try:
            with open(self.heartbeat_file, 'r') as f:
                timestamp = float(f.read().strip())
            
            # Heartbeat fresh if less than 5 seconds old
            age = time.time() - timestamp
            return age < 5
        except:
            return False
    
    def generate_resident_jsx(self):
        """Generate resident script that stays alive and listens for commands"""
        jsx = []
        jsx.append("// Image Tea Resident Script for Illustrator")
        jsx.append("// This script stays alive and executes commands from Image Tea")
        jsx.append("")
        
        # Paths
        heartbeat_path = self.heartbeat_file.replace('\\', '/')
        command_path = self.command_file.replace('\\', '/')
        
        jsx.append(f"var heartbeatFile = File('{heartbeat_path}');")
        jsx.append(f"var commandFile = File('{command_path}');")
        jsx.append("var running = true;")
        jsx.append("var config = {};")
        jsx.append("var originalFileName = '';")
        jsx.append("")
        
        jsx.append("function updateHeartbeat() {")
        jsx.append("    heartbeatFile.open('w');")
        jsx.append("    heartbeatFile.write(new Date().getTime() / 1000);")
        jsx.append("    heartbeatFile.close();")
        jsx.append("}")
        jsx.append("")
        
        jsx.append("function safeOpen(filePath) {")
        jsx.append("    var f = new File(filePath);")
        jsx.append("    if (!f.exists) throw new Error('File not found: ' + filePath);")
        jsx.append("    var ext = f.name.match(/\\.([^.]+)$/);")
        jsx.append("    ext = ext ? ext[1].toLowerCase() : '';")
        jsx.append("    try {")
        jsx.append("        switch(ext) {")
        jsx.append("            case 'ai': return app.open(f, DocumentColorSpace.RGB);")
        jsx.append("            case 'eps': case 'epsf': return app.open(f, DocumentColorSpace.RGB);")
        jsx.append("            case 'svg': return app.open(f, DocumentColorSpace.RGB);")
        jsx.append("            case 'pdf': return app.open(f, DocumentColorSpace.RGB);")
        jsx.append("            default: return app.open(f);")
        jsx.append("        }")
        jsx.append("    } catch(e) {")
        jsx.append("        return app.open(f);")
        jsx.append("    }")
        jsx.append("}")
        jsx.append("")
        
        jsx.append("function executeCommand(cmd) {")
        jsx.append("    try {")
        jsx.append("        var preset_id = cmd.preset_id;")
        jsx.append("        var steps = cmd.steps;")
        jsx.append("        var files = cmd.files || [];")
        jsx.append("        var isBatch = cmd.is_batch || false;")
        jsx.append("        var isSingleRunWithFile = cmd.is_single_run_with_file || false;")
        jsx.append("        config = cmd.config || {};")
        jsx.append("        config.outputPath = cmd.output_path || '';")
        jsx.append("        config.prefix = (cmd.config && cmd.config.output_prefix) || '';")
        jsx.append("        config.suffix = (cmd.config && cmd.config.output_suffix) || '';")
        jsx.append("")
        jsx.append("        if (isBatch) {")
        jsx.append("            for (var i = 0; i < files.length; i++) {")
        jsx.append("                var doc = safeOpen(files[i]);")
        jsx.append("                originalFileName = doc.name.replace(/\\.[^.]+$/, '');")
        jsx.append("                // Sanitize filename like Illustrator does when exporting")
        jsx.append("                originalFileName = originalFileName.replace(/\\s+/g, '-');")
        jsx.append("                executeSteps(steps);")
        jsx.append("                doc.close(SaveOptions.DONOTSAVECHANGES);")
        jsx.append("            }")
        jsx.append("        } else if (isSingleRunWithFile && files.length > 0) {")
        jsx.append("            var doc = safeOpen(files[0]);")
        jsx.append("            originalFileName = doc.name.replace(/\\.[^.]+$/, '');")
        jsx.append("            // Sanitize filename like Illustrator does when exporting")
        jsx.append("            originalFileName = originalFileName.replace(/\\s+/g, '-');")
        jsx.append("            executeSteps(steps);")
        jsx.append("            doc.close(SaveOptions.DONOTSAVECHANGES);")
        jsx.append("        } else {")
        jsx.append("            originalFileName = app.activeDocument.name.replace(/\\.[^.]+$/, '');")
        jsx.append("            // Sanitize filename like Illustrator does when exporting")
        jsx.append("            originalFileName = originalFileName.replace(/\\s+/g, '-');")
        jsx.append("            executeSteps(steps);")
        jsx.append("        }")
        jsx.append("        ")
        jsx.append("        running = false;")
        jsx.append("    } catch(e) {")
        jsx.append("        running = false;")
        jsx.append("    }")
        jsx.append("}")
        jsx.append("")
        
        jsx.append("function executeSteps(steps) {")
        jsx.append("    for (var i = 0; i < steps.length; i++) {")
        jsx.append("        var step = steps[i];")
        jsx.append("        if (step.type == 'Action') {")
        jsx.append("            app.doScript(step.name, step.action_set, false);")
        jsx.append("        } else if (step.type == 'Delay') {")
        jsx.append("            $.sleep(step.delay);")
        jsx.append("        } else if (step.type == 'Script') {")
        jsx.append("            if (step.code && step.code.length > 0) {")
        jsx.append("                eval(step.code);")
        jsx.append("            }")
        jsx.append("            if (step.delay > 0) $.sleep(step.delay);")
        jsx.append("        } else if (step.type == 'Export') {")
        jsx.append("            executeExport(step.export_format, step.export_setting || 100);")
        jsx.append("        }")
        jsx.append("    }")
        jsx.append("}")
        jsx.append("")
        
        jsx.append("function getUniqueFilePath(basePath) {")
        jsx.append("    var file = new File(basePath);")
        jsx.append("    var folder = file.parent;")
        jsx.append("    var originalName = file.name;")
        jsx.append("    var nameWithoutExt = originalName.replace(/\\.[^.]+$/, '');")
        jsx.append("    var ext = originalName.match(/\\.[^.]+$/)[0];")
        jsx.append("    ")
        jsx.append("    // Scan folder for similar files and find max numbering")
        jsx.append("    // Normalize name: remove all non-alphanumeric for loose matching")
        jsx.append("    var coreNormalized = nameWithoutExt.replace(/[^a-z0-9]/gi, '').toLowerCase();")
        jsx.append("    var maxNum = 0;")
        jsx.append("    var baseExists = false;")
        jsx.append("    ")
        jsx.append("    var folderFiles = folder.getFiles();")
        jsx.append("    for (var i = 0; i < folderFiles.length; i++) {")
        jsx.append("        if (folderFiles[i] instanceof File) {")
        jsx.append("            var fname = folderFiles[i].name;")
        jsx.append("            var fext = fname.match(/\\.[^.]+$/);")
        jsx.append("            if (!fext || fext[0].toLowerCase() != ext.toLowerCase()) continue;")
        jsx.append("            ")
        jsx.append("            var fbase = fname.replace(/\\.[^.]+$/, '');")
        jsx.append("            var fbaseNormalized = fbase.replace(/[^a-z0-9]/gi, '').toLowerCase();")
        jsx.append("            ")
        jsx.append("            // Check if base name matches (without numbering)")
        jsx.append("            if (fbaseNormalized == coreNormalized) {")
        jsx.append("                baseExists = true;")
        jsx.append("            }")
        jsx.append("            ")
        jsx.append("            // Check if numbered variant: ends with _###")
        jsx.append("            var numMatch = fbase.match(/_([0-9]{3})$/);")
        jsx.append("            if (numMatch) {")
        jsx.append("                var fbaseWithoutNum = fbase.replace(/_[0-9]{3}$/, '');")
        jsx.append("                var fbaseWithoutNumNormalized = fbaseWithoutNum.replace(/[^a-z0-9]/gi, '').toLowerCase();")
        jsx.append("                if (fbaseWithoutNumNormalized == coreNormalized) {")
        jsx.append("                    var num = parseInt(numMatch[1], 10);")
        jsx.append("                    if (num > maxNum) maxNum = num;")
        jsx.append("                }")
        jsx.append("            }")
        jsx.append("        }")
        jsx.append("    }")
        jsx.append("    ")
        jsx.append("    // If base exists or numbered files exist, use next number")
        jsx.append("    if (baseExists || maxNum > 0) {")
        jsx.append("        var nextNum = maxNum + 1;")
        jsx.append("        var numStr = ('000' + nextNum).slice(-3);")
        jsx.append("        var numberedName = nameWithoutExt + '_' + numStr + ext;")
        jsx.append("        var numberedFile = new File(folder + '/' + numberedName);")
        jsx.append("        return numberedFile;")
        jsx.append("    }")
        jsx.append("    ")
        jsx.append("    // Check if base file exists - if yes, create _001")
        jsx.append("    if (file.exists) {")
        jsx.append("        var numberedName = nameWithoutExt + '_001' + ext;")
        jsx.append("        return new File(folder + '/' + numberedName);")
        jsx.append("    }")
        jsx.append("    ")
        jsx.append("    return file;")
        jsx.append("}")
        jsx.append("")
        
        jsx.append("function executeExport(format, exportSetting) {")
        jsx.append("    try {")
        jsx.append("        var doc = app.activeDocument;")
        jsx.append("        var basePath;")
        jsx.append("        var exportFile;")
        jsx.append("        ")
        jsx.append("        if (format == 'PNG') {")
        jsx.append("            basePath = config.outputPath + '/' + config.prefix + originalFileName + config.suffix + '.png';")
        jsx.append("            exportFile = getUniqueFilePath(basePath);")
        jsx.append("            var pngOptions = new ExportOptionsPNG24();")
        jsx.append("            pngOptions.transparency = true;")
        jsx.append("            doc.exportFile(exportFile, ExportType.PNG24, pngOptions);")
        jsx.append("        } else if (format == 'JPG' || format == 'JPEG') {")
        jsx.append("            basePath = config.outputPath + '/' + config.prefix + originalFileName + config.suffix + '.jpg';")
        jsx.append("            exportFile = getUniqueFilePath(basePath);")
        jsx.append("            var jpgOptions = new ExportOptionsJPEG();")
        jsx.append("            jpgOptions.qualitySetting = exportSetting || 100;")
        jsx.append("            doc.exportFile(exportFile, ExportType.JPEG, jpgOptions);")
        jsx.append("        } else if (format == 'AI') {")
        jsx.append("            basePath = config.outputPath + '/' + config.prefix + originalFileName + config.suffix + '.ai';")
        jsx.append("            exportFile = getUniqueFilePath(basePath);")
        jsx.append("            var aiOptions = new IllustratorSaveOptions();")
        jsx.append("            doc.saveAs(exportFile, aiOptions);")
        jsx.append("        } else if (format == 'EPS') {")
        jsx.append("            basePath = config.outputPath + '/' + config.prefix + originalFileName + config.suffix + '.eps';")
        jsx.append("            exportFile = getUniqueFilePath(basePath);")
        jsx.append("            var epsOptions = new EPSSaveOptions();")
        jsx.append("            epsOptions.compatibility = eval(exportSetting);")
        jsx.append("            doc.saveAs(exportFile, epsOptions);")
        jsx.append("        } else if (format == 'PDF') {")
        jsx.append("            basePath = config.outputPath + '/' + config.prefix + originalFileName + config.suffix + '.pdf';")
        jsx.append("            exportFile = getUniqueFilePath(basePath);")
        jsx.append("            var pdfOptions = new PDFSaveOptions();")
        jsx.append("            doc.saveAs(exportFile, pdfOptions);")
        jsx.append("        } else if (format == 'SVG') {")
        jsx.append("            basePath = config.outputPath + '/' + config.prefix + originalFileName + config.suffix + '.svg';")
        jsx.append("            exportFile = getUniqueFilePath(basePath);")
        jsx.append("            var svgOptions = new ExportOptionsSVG();")
        jsx.append("            svgOptions.embedRasterImages = false;")
        jsx.append("            svgOptions.preserveEditability = false;")
        jsx.append("            doc.exportFile(exportFile, ExportType.SVG, svgOptions);")
        jsx.append("        }")
        jsx.append("        $.sleep(500);")
        jsx.append("    } catch(e) {")
        jsx.append("        alert('ERROR in executeExport: ' + e.toString() + '\\nLine: ' + e.line + '\\nFormat: ' + format);")
        jsx.append("    }")
        jsx.append("}")
        jsx.append("")
        
        jsx.append("function checkCommand() {")
        jsx.append("    if (commandFile.exists) {")
        jsx.append("        commandFile.open('r');")
        jsx.append("        var cmdText = commandFile.read();")
        jsx.append("        commandFile.close();")
        jsx.append("        commandFile.remove();")
        jsx.append("        ")
        jsx.append("        try {")
        jsx.append("            var cmd = eval('(' + cmdText + ')');")
        jsx.append("            if (cmd.command == 'STOP') {")
        jsx.append("                running = false;")
        jsx.append("            } else if (cmd.command == 'EXECUTE') {")
        jsx.append("                executeCommand(cmd);")
        jsx.append("            }")
        jsx.append("        } catch(e) {")
        jsx.append("            // Silent error")
        jsx.append("        }")
        jsx.append("    }")
        jsx.append("}")
        jsx.append("")
        
        jsx.append("// Main loop")
        jsx.append("while (running) {")
        jsx.append("    updateHeartbeat();")
        jsx.append("    checkCommand();")
        jsx.append("    $.sleep(500);")
        jsx.append("}")
        jsx.append("")
        jsx.append("// Cleanup")
        jsx.append("if (heartbeatFile.exists) heartbeatFile.remove();")
        
        jsx_code = "\n".join(jsx)
        
        with open(self.resident_jsx, 'w', encoding='utf-8') as f:
            f.write(jsx_code)
        
        print(f"Generated resident JSX: {self.resident_jsx}")
        return self.resident_jsx
    
    def send_command(self, preset_id, preset_steps, source_files, output_path, config, is_single_run_with_file=False):
        """Send command to resident script
        
        Args:
            preset_id: Preset ID
            preset_steps: Pre-validated list of steps (already filtered for valid action_ids)
            source_files: List of source files
            output_path: Output path
            config: Config dict
            is_single_run_with_file: Boolean
        """
        is_batch = len(source_files) > 0 and not is_single_run_with_file
        
        # Build steps array
        steps = []
        for step in preset_steps:
            action_detail = self.db.get_action_by_id(step['action_id'])
            if action_detail:
                action_type = action_detail.get('type', 'Action')
                
                step_data = {
                    'name': action_detail['name'],
                    'type': action_type
                }
                
                if action_type == 'Action':
                    step_data['action_set'] = step['action_set']
                elif action_type == 'Delay':
                    step_data['delay'] = action_detail.get('delay', 0)
                elif action_type == 'Script':
                    js_code = action_detail.get('javascript_code', '')
                    if not js_code or not js_code.strip():
                        print(f"WARNING: Script action '{action_detail.get('name', '?')}' has no javascript_code, skipping...")
                        continue  # Skip this step entirely
                    step_data['code'] = js_code
                    step_data['delay'] = action_detail.get('delay', 0)
                elif action_type == 'Export':
                    export_format = action_detail.get('export_format', 'PNG')
                    export_setting = action_detail.get('export_setting', 100)
                    
                    # Translate EPS index to Compatibility constant in Python
                    if export_format == 'EPS':
                        eps_index = export_setting
                        if eps_index not in self.eps_version_map:
                            raise ValueError(f"Invalid EPS version index: {eps_index}. Must be 0-12.")
                        export_setting = self.eps_version_map[eps_index]
                        print(f"DEBUG: EPS index {eps_index} -> {export_setting}")
                    
                    step_data['export_format'] = export_format
                    step_data['export_setting'] = export_setting
                    print(f"DEBUG: Export step added - format={export_format}, setting={export_setting}")
                
                steps.append(step_data)
        
        print(f"DEBUG: Total steps built: {len(steps)}")
        print(f"DEBUG: Export steps count: {sum(1 for s in steps if s['type'] == 'Export')}")
        
        # Build command
        command = {
            'command': 'EXECUTE',
            'preset_id': preset_id,
            'files': [f.replace('\\', '/') for f in source_files],
            'output_path': output_path.replace('\\', '/'),
            'config': config,
            'steps': steps,
            'is_batch': is_batch,
            'is_single_run_with_file': is_single_run_with_file
        }
        
        # Write command file
        with open(self.command_file, 'w', encoding='utf-8') as f:
            json.dump(command, f, indent=2)
        
        print(f"Command sent to resident script")
        return self.command_file
    
    def generate_jsx(self, preset_id, source_files, output_path, config, is_single_run_with_file=False):
        """Generate JSX file for Illustrator - Use resident if available
        
        Args:
            preset_id: ID preset from database
            source_files: List of file paths to process (can be empty for single run)
            output_path: Output folder path
            config: Config dict (prefix, suffix, etc)
            is_single_run_with_file: True if single run mode with loaded file
        
        Returns:
            tuple: (jsx_path, is_resident) - path to JSX and whether using resident
        """
        preset_steps = self.db.get_preset_steps(preset_id)
        
        if not preset_steps:
            print(f"WARNING: No steps found for preset {preset_id}")
            return (None, False)
        
        # Filter out steps that reference non-existent actions
        valid_steps = []
        for step in preset_steps:
            action_detail = self.db.get_action_by_id(step['action_id'])
            if action_detail:
                valid_steps.append(step)
            else:
                print(f"WARNING: Skipping step {step.get('order_index', '?')} - action_id={step['action_id']} no longer exists in database")
        
        if not valid_steps:
            print(f"ERROR: All steps in preset {preset_id} reference deleted/non-existent actions")
            return (None, False)
        
        # Debug log step types
        step_types = []
        for s in valid_steps:
            action_detail = self.db.get_action_by_id(s['action_id'])
            step_types.append(action_detail.get('type', 'Unknown') if action_detail else 'Unknown')
        print(f"DEBUG Illustrator: Generating JSX for preset {preset_id} with {len(valid_steps)} steps")
        print(f"DEBUG Illustrator: Step types: {step_types}")
        
        # ALWAYS regenerate resident script to get latest code
        print("Regenerating resident JSX with latest code...")
        resident_path = self.generate_resident_jsx()
        
        # Check if resident is alive
        if self.is_resident_alive():
            print("Resident script detected - sending command")
            self.send_command(preset_id, valid_steps, source_files, output_path, config, is_single_run_with_file)
            return (None, True)  # No JSX file needed, using resident
        
        # Send initial command for new resident
        print("Starting new resident script")
        self.send_command(preset_id, valid_steps, source_files, output_path, config, is_single_run_with_file)
        
        return (resident_path, False)  # Return resident JSX to launch
