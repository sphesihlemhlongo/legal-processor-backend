#!/usr/bin/env python3
"""
Command-line interface for batch processing legal documents
Usage: python cli.py input_folder output_folder
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path
from typing import List

from reader import DocumentReader
from processor import DocumentProcessor
from llm_client import LLMClient
from writer import DocumentWriter
from logger_config import get_logger

logger = get_logger(__name__)

class CLIProcessor:
    """Command-line interface for document processing"""
    
    def __init__(self):
        self.reader = DocumentReader()
        self.processor = DocumentProcessor()
        self.llm_client = LLMClient()
        self.writer = DocumentWriter()
    
    async def process_folder(self, input_folder: str, output_folder: str):
        """Process all documents in a folder"""
        try:
            input_path = Path(input_folder)
            output_path = Path(output_folder)
            
            if not input_path.exists():
                raise FileNotFoundError(f"Input folder not found: {input_folder}")
            
            # Create output directory
            output_path.mkdir(parents=True, exist_ok=True)
            
            # Find all supported documents
            supported_extensions = ['.pdf', '.docx', '.txt']
            documents = []
            
            for ext in supported_extensions:
                documents.extend(input_path.glob(f"*{ext}"))
            
            if not documents:
                print(f"No supported documents found in {input_folder}")
                return
            
            print(f"Found {len(documents)} documents to process")
            
            # Process each document
            for doc_path in documents:
                await self.process_single_document(doc_path, output_path)
            
            print("Batch processing completed!")
            
        except Exception as e:
            logger.error(f"Batch processing error: {str(e)}")
            raise
    
    async def process_single_document(self, doc_path: Path, output_folder: Path):
        """Process a single document"""
        try:
            print(f"\nProcessing: {doc_path.name}")
            
            # Read document
            content = self.reader.read_document(str(doc_path), doc_path.name)
            
            # Create sections
            sections = self.processor.create_sections(content)
            print(f"  Split into {len(sections)} sections")
            
            # Process each section
            plain_english_parts = []
            summary_parts = []
            
            for i, section in enumerate(sections):
                print(f"  Processing section {i+1}/{len(sections)}")
                
                # Plain English conversion
                plain_prompt = self.processor.create_plain_english_prompt(section)
                plain_result = await self.llm_client.call_llm_async(plain_prompt)
                plain_english_parts.append(plain_result)
                
                # Summary conversion
                summary_prompt = self.processor.create_summary_prompt(section)
                summary_result = await self.llm_client.call_llm_async(summary_prompt)
                summary_parts.append(summary_result)
            
            # Write output files
            base_name = doc_path.stem
            
            plain_filename = f"{base_name}_plainEnglish.docx"
            summary_filename = f"{base_name}_summary.docx"
            
            plain_path = output_folder / plain_filename
            summary_path = output_folder / summary_filename
            
            self.writer.write_docx(
                "\n\n".join(plain_english_parts),
                str(plain_path)
            )
            
            self.writer.write_docx(
                "\n\n".join(summary_parts),
                str(summary_path)
            )
            
            print(f"  ✓ Generated: {plain_filename}")
            print(f"  ✓ Generated: {summary_filename}")
            
        except Exception as e:
            logger.error(f"Error processing {doc_path.name}: {str(e)}")
            print(f"  ✗ Error: {str(e)}")

def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(description="Process legal documents into plain English and summaries")
    parser.add_argument("input_folder", help="Folder containing documents to process")
    parser.add_argument("output_folder", help="Folder to save processed documents")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    processor = CLIProcessor()
    
    try:
        asyncio.run(processor.process_folder(args.input_folder, args.output_folder))
    except KeyboardInterrupt:
        print("\nProcessing interrupted by user")
    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()